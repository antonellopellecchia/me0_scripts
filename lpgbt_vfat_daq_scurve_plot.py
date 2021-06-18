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

    plot_filename_prefix = args.filename.split(".txt")[0]
    file = open(args.filename)
    scurve_result = {}
    for line in file.readlines():
        if "vfatN" in line:
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
        fig, ax = plt.subplots()
        plt.xlabel('Charge')
        plt.ylabel('# Fired Events / # Total Events')
        for channel in args.channels:
            channel = int(channel)
            charge = range(0,256)
            frac = []
            for c in charge:
                frac.append(scurve_result[vfat][channel][c])
            ax.plot(charge, frac, 'o', label="Channel %d"%channel)
        leg = ax.legend(loc='center right', ncol=2)
        plt.title("VFAT# %02d"%vfat)
        plt.savefig((plot_filename_prefix+"_VFAT%02d.pdf")%vfat)





