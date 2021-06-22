from rw_reg_lpgbt import *
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import os, sys, glob
import argparse

if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='Plotting VFAT DAQ SCurve')
    parser.add_argument("-f", "--filename", action="store", dest="filename", help="SCurve result filename")
    parser.add_argument("-c", "--channels", action="store", nargs="+", dest="channels", help="Channels to plot for each VFAT")
    args = parser.parse_args()

    if args.channels is None:
        print(Colors.YELLOW + "Enter channel list to plot SCurves" + Colors.ENDC)
        sys.exit()

    plot_filename_prefix = args.filename.split(".txt")[0]
    file = open(args.filename)
    scurve_result = {}
    for line in file.readlines():
        if "vfat" in line:
            continue
        vfat = int(line.split()[0])
        channel = int(line.split()[1])
        charge = int(line.split()[2])
        fired = int(line.split()[3])
        events = int(line.split()[4])
        if vfat not in scurve_result:
            scurve_result[vfat] = {}
        if channel not in scurve_result[vfat]:
            scurve_result[vfat][channel] = {}
        if fired == -9999 or events == -9999 or events == 0:
            scurve_result[vfat][channel][charge] = 0
        else:
            scurve_result[vfat][channel][charge] = float(fired)/float(events)
    file.close()

    for vfat in scurve_result:
        fig, axs = plt.subplots()
        plt.xlabel('Channel')
        plt.ylabel('Charge')
        plt.xlim(0,128)
        plt.ylim(0,256)

        plot_data = []
        for charge in range(0,256):
            data = []
            for channel in range(0,128):
                if channel not in scurve_result[vfat]:
                    data.append(0)
                elif charge not in scurve_result[vfat][channel]:
                    data.append(0)
                else:
                    data.append(scurve_result[vfat][channel][charge])
            plot_data.append(data)
        plot = axs.imshow(plot_data, cmap='plasma',interpolation="nearest", aspect="auto")
        fig.colorbar(plot, ax=axs)
        plt.title("VFAT# %02d"%vfat)
        plt.savefig((plot_filename_prefix+"_map_VFAT%02d.pdf")%vfat)

    for vfat in scurve_result:
        fig, ax = plt.subplots()
        plt.xlabel('Charge')
        plt.ylabel('# Fired Events / # Total Events')
        plt.ylim(-0.1,1.1)
        for channel in args.channels:
            channel = int(channel)
            if channel not in scurve_result[vfat]:
                print (Colors.YELLOW + "Channel %d not in SCurve scan"%channel + Colors.ENDC)
                continue
            charge = range(0,256)
            charge_plot = []
            frac = []
            for c in charge:
                if c in scurve_result[vfat][channel]:
                    charge_plot.append(c)
                    frac.append(scurve_result[vfat][channel][c])
            ax.plot(charge_plot, frac, 'o', label="Channel %d"%channel)
        leg = ax.legend(loc='center right', ncol=2)
        plt.title("VFAT# %02d"%vfat)
        plt.savefig((plot_filename_prefix+"_VFAT%02d.pdf")%vfat)










