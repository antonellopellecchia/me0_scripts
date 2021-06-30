from rw_reg_lpgbt import *
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import os, sys, glob
import argparse

if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='Plotting VFAT HitMap')
    parser.add_argument("-f", "--filename", action="store", dest="filename", help="Hit/Noise map result filename")
    parser.add_argument("-t", "--type", action="store", dest="type", help="type = hit or noise")
    args = parser.parse_args()

    if args.type not in ["hit", "noise"]:
        print (Colors.YELLOW + "Only hit or noise options allowed for type" + Colors.ENDC)
        sys.exit()

    plot_filename_prefix = args.filename.split(".txt")[0]
    file = open(args.filename)
    hitmap_result = {}
    for line in file.readlines():
        if "vfat" in line:
            continue
        vfat = int(line.split()[0])
        channel = int(line.split()[1])
        fired = int(line.split()[2])
        events = int(line.split()[3])
        if vfat not in hitmap_result:
            hitmap_result[vfat] = {}
        if fired == -9999 or events == -9999 or events == 0:
            hitmap_result[vfat][channel] = 0
        else:
            hitmap_result[vfat][channel] = float(fired)/float(events)
    file.close()

    fig, ax = plt.subplots()
    plt.xlabel('Channel')
    plt.ylabel('# Fired Events / # Total Events')
    plt.ylim(-0.1,1.1)
    channel_plot = range(0,128)
    if args.type == "hit":
        plt.title("Channel Hit Map")
    else:
        plt.title("Channel Noise Map")
    for vfat in hitmap_result:
        frac = []
        for channel in channel_plot:
            frac.append(hitmap_result[vfat][channel])
        ax.plot(channel_plot, frac, 'o', label="VFAT %d"%vfat)
        leg = ax.legend(loc='center right', ncol=2)
    plt.savefig(plot_filename_prefix+"_map.pdf")





