from sys import stdout
import itertools as it
import numpy as np
import subprocess


class SpiceGenerator(object):

    def __init__(self, filename=''):
        # define necessary spice grammar
        self.__commentfrmt = '* {c}'
        self.__bcommentfrmt = '\n*\n* {c}\n*'

        # these two are set once we know how much to pad
        self.__rfrmt = ''
        self.__vfrmt = ''

        # init component counters
        self.r_counter = 0
        self.v_counter = 0

        # create file handle
        if filename == '':
            self.file = stdout
        else:
            self.file = open('{}.cir'.format(filename), 'w')

    def create_script(self, mesh, conductance):
        # mesh size
        self.mesh_size = len(mesh)
        self.set_id_pads(int(np.log10(self.mesh_size**2)+1))

        full_range = range(self.mesh_size)
        short_range = range(self.mesh_size-1)

        # generate row resistors
        self.add_block_comment("Row Resistors")
        for i, j in it.product(full_range, short_range):
            self.add_r((i, j), (i, j+1), conductance, horizontal=True)

        # generate column resistors
        self.add_block_comment("Column Resistors")
        for i, j in it.product(short_range, full_range):
            self.add_r((i, j), (i+1, j), conductance, horizontal=False)

        # I wanted to avoid adding external voltages that goes outside
        # the boundary and doesn't attach to anything. But spice seems
        # to go haywire if I do that
        add_extra_ammeters = True
        ammeters = []
        # generate nodes with 4 0V sources
        self.add_block_comment("Node subcircuits")
        for i, j in it.product(full_range, full_range):
            self.add_comment("Node " + str((i,j)))
            if add_extra_ammeters or j > 0:
                ammeters.append(self.add_v((i, j), (i, j), v=0, dir1='E'))
            if add_extra_ammeters or j < self.mesh_size-1:
                ammeters.append(self.add_v((i, j), (i, j), v=0, dir1='W'))
            if add_extra_ammeters or i > 0:
                ammeters.append(self.add_v((i, j), (i, j), v=0, dir1='N'))
            if add_extra_ammeters or i < self.mesh_size-1:
                ammeters.append(self.add_v((i, j), (i, j), v=0, dir1='S'))

        # generate row voltages
        self.add_block_comment("Voltage Sources")
        for i, j in it.product(full_range, full_range):
            self.add_point_v((i, j), mesh[i][j])

        # self.generate measurement/analysis components
        self.add_block_comment("Analysis code")
        self.add_transtmt()
        for a in ammeters:
            self.add_printstmt(a)

        self.file.close()

    #
    # codegen Functions
    #
    def add_transtmt(self):
        self.gen(self.__tranfrmt.format())

    def add_printstmt(self, symbol):
        self.gen(self.__printfrmt.format(symbol=symbol))

    def add_r(self, grid_idx1, grid_idx2, r, horizontal, name=''):
        if horizontal:
            format_str = self.__hrfrmt
        else:
            format_str = self.__vrfrmt
        self.gen(format_str.format(i=self.r_counter,
                                   uname=self.concat_name(name),
                                   n1=grid_idx1,
                                   n2=grid_idx2,
                                   r=r))

        self.r_counter += 1

    def add_v(self, grid_idx1, grid_idx2, v, dir1='', dir2='', name=''):
        ret = ''
        if v >= 0:
            ret = self.gen(self.__vfrmt.format(i=self.v_counter,
                                         uname=self.concat_name(name),
                                         n1=grid_idx1,
                                         d1=dir1,
                                         n2=grid_idx2,
                                         d2=dir2,
                                         v=v))
        elif v < 0:
            ret = self.gen(self.__vfrmt.format(i=self.v_counter,
                                         uname=self.concat_name(name),
                                         n1=grid_idx2,
                                         d1=dir1,
                                         n2=grid_idx1,
                                         d2=dir2,
                                         v=-v))
        self.v_counter += 1
        return ret

    def add_point_v(self, grid_idx, v, name=''):
        if v > 0:
            self.gen(self.__pvfrmt.format(i=self.v_counter,
                                          uname=self.concat_name(name),
                                          n=grid_idx,
                                          v=v))
            self.v_counter += 1


    def add_block_comment(self, comment):
        self.gen(self.__bcommentfrmt.format(c=comment))

    def add_comment(self, comment):
        self.gen(self.__commentfrmt.format(c=comment))

    #
    # simulator utils
    #
    def run(self):
        subprocess.run('ngspice -b test.cir -o test.out', shell=True)

    def get_results(self):
        w = self.mesh_size
        h = self.mesh_size
        results = np.zeros((h,w))
        grep_cmd = 'grep v{:0>2} test.out -A2 | tail -n1 | tr "\t" " " | cut -d" " -f"3"'
        vid = 0
        for i, j in it.product(range(h), range(w)):
            for _, d in zip(range(4), ['E', 'W', 'N', 'S']):
                tmp_val = float(subprocess.check_output(
                                       grep_cmd.format(vid),
                                       shell=True))
                print((i,j,d), tmp_val)
                results[i][j] += tmp_val
                vid += 1

        return results



    #
    # Utility Functions
    #
    def flatten_idx(self, idx):
        return idx[0]*self.mesh_size+idx[1]

    def concat_name(self, name):
        if name != '':
            return '_{}'.format(name)
        else:
            return ''

    def gen(self, s):
        self.file.write('{}\n'.format(s))
        return s.split()[0]

    def set_id_pads(self, width):
        ps = str(width)
        self.__hrfrmt = 'R{i:0>'+ps+'}{uname} N{n1[0]:}_{n1[1]:}E N{n2[0]:}_{n2[1]:}W {r}'
        self.__vrfrmt = 'R{i:0>'+ps+'}{uname} N{n1[0]:}_{n1[1]:}S N{n2[0]:}_{n2[1]:}N {r}'
        self.__vfrmt = 'V{i:0>'+ps+'}{uname} N{n1[0]:}_{n1[1]:}{d1} N{n2[0]:}_{n2[1]:}{d2} DC {v}'
        self.__pvfrmt = 'V{i:0>'+ps+'}{uname} N{n[0]:}_{n[1]:} 0 DC {v}'
        self.__tranfrmt = '.TRAN 1NS 11NS 10NS 10NS'
        self.__printfrmt = '.PRINT TRAN I({symbol})'
