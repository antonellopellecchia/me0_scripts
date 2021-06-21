import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import os, sys, glob
import argparse
from scipy.optimize import curve_fit
from scipy.special import erf
from math import sqrt
from tqdm import tqdm
import warnings

plt.rcParams.update({'font.size': 22}) # Increase font size

def dictToArray(dictionary, vfatNumber, channel):
    '''
    Returns (256, 2) ndarray.
    column 0 = injected charge
    column 1 = ratio of fired events / total events
    '''
    return np.array(list(dictionary[vfatNumber][channel].items()))

def scurveFunc(injCharge, A, ch_pedestal, mean, sigma):
    '''
    Modified error function.
    injCharge = injected charge
    '''
    
    pedestal = np.zeros(256)
    if ch_pedestal > 0.0:
        pedestal.fill(ch_pedestal)
        
    maxCharge = np.maximum(pedestal, injCharge)

    return A * erf(np.true_divide((maxCharge - mean), sigma * sqrt(2))) + A

def DACToCharge(injCharge):
    '''
    Slope and intercept for all VFATs from the CAL_DAC 
    cal file needs to be added. Default values here are
    a rough average of cal data.
    '''
    slope     = 0.22 # fC/DAC
    intercept = 54   # fC
    injCharge = np.multiply(slope, injCharge)
    injCharge = injCharge + intercept 

    return injCharge

def fit_scurve(vfatList, scurve_result, plot_filename_prefix, directoryName, verbose , plotAll):
    vfatCounter   = 0 
    scurveParams = np.ndarray((len(vfatList), 128, 2))
    
    for vfat in vfatList:
        print('Fitting data for VFAT%2d' % vfat)
        fitFileName = directoryName + '/' + plot_filename_prefix + ("_VFAT%02d_" % vfat) + "fitResults.txt"
        file_out = open(fitFileName, "w+")
        file_out.write("========= Results for VFAT%2d =========\n" % vfat)
        print("========= Processing data for VFAT%2d =========\n" % vfat)
        file_out.write("Channel    Mean    ENC\n")
            
        for channel in tqdm(range(128)):
            scurveData      = dictToArray(scurve_result, vfat, channel) # transfer data from dictionary to array
            scurveData[:,0] = DACToCharge(scurveData[:,0]) # convert to fC
        
            params, covMatrix = curve_fit(scurveFunc, scurveData[:,0], scurveData[:,1], p0=[1, 0, 60, 0.4], maxfev=100000) # fit data; returns optimized parameters and covariance matrix
            
            file_out.write("%d    %.4f    %.4f \n" % (channel, params[2], params[3]))
            scurveParams[vfatCounter, channel, 0] = params[3] # store channel ENC
            scurveParams[vfatCounter, channel, 1] = params[2] # store channel mean
            
            if verbose == True:
                print('Channel %i Average ENC: %.4f ' % (channel, scurveParams[vfatCounter, channel, 0]))
                print('Channel %i Average mean: %.4f ' % (channel, scurveParams[vfatCounter, channel, 1]))
            else:
                pass
            
            if plotAll == True:
                fig, ax = plt.subplots(figsize = (16,10))
                plt.xlabel('Charge (fC)')
                plt.ylabel('Fired Events / Total Events')
                ax.plot(scurveData[:,0], scurveData[:,1], 'o', markersize= 6, label = 'Channel %d' % channel) # plot raw data
                ax.plot(scurveData[:,0], scurveFunc(scurveData[:,0], *params), 'r-', label='fit')
                props = dict(boxstyle='round', facecolor='white',edgecolor='lightgrey', alpha=1)
                textstr = '\n'.join((
                    r'Threshold: $\mu=%.4f$ (fC)' % (params[2], ),
                    r'ENC: $\sigma=%.4f$ (fC)' % (params[3], ),))
                ax.text(0.663, 0.7, textstr, transform=ax.transAxes, fontsize=22, verticalalignment='top', bbox=props)
                ax.set_title('VFAT0%d' % vfat)
                leg = ax.legend(loc='center right', ncol=2)
                plt.grid()
                fig.tight_layout()
                plt.savefig(directoryName + '/scurveFit_VFAT%d_channel%d.pdf' % (vfat, channel))
                plt.close() # clear the plot
            else:
                pass
        
        # average values for all channels    
        avgENC = np.average(scurveParams[vfatCounter, :, 0])
        avgMean = np.average(scurveParams[vfatCounter, :, 1])


        print("========= Summary =========\n")
        print("Average ENC: %.4f (fC)" % avgENC)
        print("Average mean (threshold): %.4f (fC)" % avgMean)

        file_out.write("========= Summary =========\n")
        file_out.write("Average ENC: %.4f (fC)\n" % avgENC)
        file_out.write("Average mean (threshold): %.4f (fC)\n" % avgMean)

        file_out.close()
        print("Results for VFAT%0d saved in %s\n" % (vfat, fitFileName))
        vfatCounter += 1
        
    return scurveParams

def plotENCdistributions(vfatList, scurveParams, plot_filename_prefix, directoryName):
    
    fig, ax = plt.subplots(figsize = (12,10))
    ax.set_xlabel('VFAT Number')
    ax.set_ylabel('S-curve ENC (fC)')

    data = []
    for ii in range(len(vfatList)):
        data.append(scurveParams[ii, :, 0])

    ax.boxplot(data, patch_artist=True)
    
    plt.xticks(np.arange(1, len(vfatList) + 1), vfatList) # replace ticks with vfat number
    ax.set_title('ENC Distributions')
    plt.grid()
    fig.tight_layout()
    plt.savefig(directoryName + '/' + plot_filename_prefix + '_scurveENCdistribution.pdf')
    print("\nENC distribution plot save at %s" % directoryName + '/' + plot_filename_prefix + '_scurveENCdistribution.pdf')

if __name__ == '__main__':
    warnings.filterwarnings("ignore") # temporarily disable warnings; infinite covariance matrix is returned when calling scipy.optimize.curve_fit(), but fit is fine

    # Parsing arguments
    parser = argparse.ArgumentParser(description='Plotting VFAT DAQ SCurve')
    parser.add_argument("-f", "--filename", action="store", dest="filename", help="SCurve result filename")
    parser.add_argument("-c", "--channels", action="store", nargs="+", dest="channels", help="Channels to plot for each VFAT")
    parser.add_argument("-p", "--plotAll", action="store_true", dest="plotAll", help="Plot Scurves and fit results for all channels in separate files")
    parser.add_argument("-v", "--verbose", action="store_true", dest="verbose", help="Increase verbosity")
    args = parser.parse_args()

    if args.channels is not None and args.plotAll == True:
        print ("Must specifiy to plot all channels (-p) or certain channels (-c), not both.")
        sys.exit()

    directoryName        = args.filename.split(".txt")[0]
    plot_filename_prefix = (directoryName.split("/"))[1]
    file = open(args.filename)


    try:
        os.makedirs(directoryName) # create directory for scurve analysis results
    except FileExistsError: # skip if directory already exists
        pass

    scurve_result = {}
    for line in file.readlines():
        if "vfatN" in line:
            continue
        vfat    = int(line.split()[0])
        channel = int(line.split()[1])
        charge  = int(line.split()[2])
        fired   = int(line.split()[3])
        events  = int(line.split()[4])
        if vfat not in scurve_result:
            scurve_result[vfat] = {}
        if channel not in scurve_result[vfat]:
            scurve_result[vfat][channel] = {}
        if fired == -9999 or events == -9999 or events == 0:
            scurve_result[vfat][channel][charge] = 0
        else:
            scurve_result[vfat][channel][charge] = float(fired)/float(events)
    file.close()
    
    vfatList     = list(scurve_result.keys())
    scurveParams = fit_scurve(vfatList, scurve_result, plot_filename_prefix, directoryName, args.verbose, args.plotAll)

    plotENCdistributions(vfatList, scurveParams, plot_filename_prefix, directoryName)

    if args.channels is not None:

        for vfat in scurve_result:
            fig, ax = plt.subplots()
            plt.xlabel('Charge (ADC)')
            plt.ylabel('# Fired Events / # Total Events')
            for channel in args.channels:
                channel = int(channel)
                charge = range(0,256)
                frac = []
                for c in charge:
                    frac.append(scurve_result[vfat][channel][c])
                ax.plot(charge, frac, 'o', label="Channel %d"%channel, markersize = 6)
            leg = ax.legend(loc='center right', ncol=2)
            plt.title("VFAT%02d"%vfat)
            plt.savefig((plot_filename_prefix+"_VFAT%d.pdf") % vfat)
