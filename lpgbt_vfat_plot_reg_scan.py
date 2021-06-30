from rw_reg_lpgbt import *
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib import cm
import numpy as np
import os, sys, glob
import argparse

if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='Plotting VFAT Register Scan')
    parser.add_argument("-f", "--filename", action="store", dest="filename", help="Register Scan result filename")
    parser.add_argument("-c", "--channels", action="store", nargs="+", dest="channels", help="Channels to plot for each VFAT")
    parser.add_argument("-d", "--dac", action="store", dest="dac", help="Register to plot")
    args = parser.parse_args()

    if args.dac is None:
        print(Colors.YELLOW + "Need Register to plot" + Colors.ENDC)
        sys.exit()
    dac = args.dac

    plot_filename_prefix = args.filename.split(".txt")[0]
    file = open(args.filename)
    dac_result = {}
    for line in file.readlines():
        if "vfat" in line:
            continue
        vfat = int(line.split()[0])
        channel = int(line.split()[1])
        reg = int(line.split()[2])
        fired = int(line.split()[3])
        events = int(line.split()[4])
        if vfat not in dac_result:
            dac_result[vfat] = {}
        if channel not in dac_result[vfat]:
            dac_result[vfat][channel] = {}
        if fired == -9999 or events == -9999 or events == 0:
            dac_result[vfat][channel][reg] = 0
        else:
            dac_result[vfat][channel][reg] = float(fired)/float(events)
    file.close()

    for vfat in dac_result:
        fig, axs = plt.subplots()
        plt.xlabel('Channel Number')
        plt.ylabel(dac + ' (DAC)')
        #plt.xlim(0,128)
        #plt.ylim(0,256)

        plot_data = []
        for reg in range(0,256):
            data = []
            for channel in range(0,128):
                if channel not in dac_result[vfat]:
                    data.append(0)
                elif reg not in dac_result[vfat][channel]:
                    data.append(0)
                else:
                    data.append(dac_result[vfat][channel][reg])
            plot_data.append(data)
        channelNum = np.arange(0, 128, 1)
        dacVals = np.arange(0, 256, 1)
        plot = axs.imshow(plot_data, extent=[min(channelNum), max(channelNum), min(dacVals), max(dacVals)], origin="lower",  cmap=cm.ocean_r,interpolation="nearest", aspect="auto")
        cbar = fig.colorbar(plot, ax=axs, pad=0.01)
        cbar.set_label('Fired Events / Total Events')
        plt.title("VFAT# %02d"%vfat)
        plt.savefig((plot_filename_prefix+"_map_VFAT%02d.pdf")%vfat)

    for vfat in dac_result:
        fig, ax = plt.subplots()
        plt.xlabel(dac)
        plt.ylabel('# Fired Events / # Total Events')
        plt.ylim(-0.1,1.1)
        for channel in args.channels:
            channel = int(channel)
            if channel not in dac_result[vfat]:
                print (Colors.YELLOW + "Channel %d not in Register scan"%channel + Colors.ENDC)
                continue
            reg = range(0,256)
            reg_plot = []
            frac = []
            for r in reg:
                if r in dac_result[vfat][channel]:
                    reg_plot.append(r)
                    frac.append(dac_result[vfat][channel][r])
            ax.plot(reg_plot, frac, 'o', label="Channel %d"%channel)
        leg = ax.legend(loc='center right', ncol=2)
        plt.title("VFAT# %02d"%vfat)
        plt.savefig((plot_filename_prefix+"_VFAT%02d.pdf")%vfat)





