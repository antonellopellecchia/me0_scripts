from rw_reg_lpgbt import *
from time import sleep, time
import sys
import argparse
import random

# VFAT number: boss/sub, ohid, gbtid, elink
# For GE2/1 GEB + Pizza
VFAT_TO_ELINK_GE21 = {
        0  : ("sub"  , 0, 1, 6),
        1  : ("sub"  , 0, 1, 24),
        2  : ("sub"  , 0, 1, 11),
        3  : ("boss" , 0, 0, 3),
        4  : ("boss" , 0, 0, 27),
        5  : ("boss" , 0, 0, 25),
        6  : ("boss" , 1, 0, 6),
        7  : ("boss" , 1, 0, 16),
        8  : ("sub"  , 1, 1, 18),
        9  : ("boss" , 1, 0, 15),
        10 : ("sub"  , 1, 1, 3),
        11 : ("sub"  , 1, 1, 17)
}

# For ME0 GEB
VFAT_TO_ELINK_ME0 = {
        0  : ("sub"  , 0, 1, 6),
        1  : ("sub"  , 0, 1, 24),
        2  : ("sub"  , 0, 1, 11),
        3  : ("boss" , 0, 0, 3),
        4  : ("boss" , 0, 0, 27),
        5  : ("boss" , 0, 0, 25),
        6  : ("sub"  , 1, 1, 6),
        7  : ("sub"  , 1, 1, 24),
        8  : ("sub"  , 1, 1, 11),
        9  : ("boss" , 1, 0, 3),
        10  : ("boss" , 1, 0, 27),
        11  : ("boss" , 1, 0, 25),
}

VFAT_TO_ELINK = VFAT_TO_ELINK_ME0

def vfat_to_oh_gbt_elink(vfat):
    lpgbt = VFAT_TO_ELINK[vfat][0]
    ohid  = VFAT_TO_ELINK[vfat][1]
    gbtid = VFAT_TO_ELINK[vfat][2]
    elink = VFAT_TO_ELINK[vfat][3]
    return lpgbt, ohid, gbtid, elink
     
def configureVfatForPulsing(vfatN, ohN, channel_list):

    if (read_backend_reg(get_rwreg_node("GEM_AMC.OH_LINKS.OH%i.VFAT%i.SYNC_ERR_CNT"%(ohN,vfatN))) > 0):
        print (Colors.RED + "Link Errors" + Colors.ENDC)
        rw_terminate()

    for i in range(128):
        write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.VFAT_CHANNELS.CHANNEL%i"%(ohN,vfatN,i)), 0x4000)  # mask all channels and disable the calpulse

    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_PULSE_STRETCH"       % (ohN , vfatN)) , 7)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_SYNC_LEVEL_MODE"     % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_SELF_TRIGGER_MODE"   % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_DDR_TRIGGER_MODE"    % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_SPZS_SUMMARY_ONLY"   % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_SPZS_MAX_PARTITIONS" % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_SPZS_ENABLE"     % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_SZP_ENABLE"      % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_SZD_ENABLE"      % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_TIME_TAG"        % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_EC_BYTES"        % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_BC_BYTES"        % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_FP_FE"           % (ohN , vfatN)) , 7)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_RES_PRE"         % (ohN , vfatN)) , 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_CAP_PRE"         % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_PT"              % (ohN , vfatN)) , 15)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_EN_HYST"         % (ohN , vfatN)) , 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_SEL_POL"         % (ohN , vfatN)) , 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_FORCE_EN_ZCC"    % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_FORCE_TH"        % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_SEL_COMP_MODE"       % (ohN , vfatN)) , 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_VREF_ADC"        % (ohN , vfatN)) , 3)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_MON_GAIN"        % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_MONITOR_SELECT"      % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_IREF"            % (ohN , vfatN)) , 32)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_THR_ZCC_DAC"     % (ohN , vfatN)) , 10)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_THR_ARM_DAC"     % (ohN , vfatN)) , 100)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_HYST"            % (ohN , vfatN)) , 5)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_LATENCY"         % (ohN , vfatN)) , 45)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_CAL_SEL_POL"     % (ohN , vfatN)) , 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_CAL_PHI"         % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_CAL_EXT"         % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_CAL_DAC"         % (ohN , vfatN)) , 50)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_CAL_MODE"        % (ohN , vfatN)) , 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_CAL_FS"          % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_CAL_DUR"         % (ohN , vfatN)) , 200)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_BIAS_CFD_DAC_2"      % (ohN , vfatN)) , 40)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_BIAS_CFD_DAC_1"      % (ohN , vfatN)) , 40)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_BIAS_PRE_I_BSF"      % (ohN , vfatN)) , 13)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_BIAS_PRE_I_BIT"      % (ohN , vfatN)) , 150)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_BIAS_PRE_I_BLCC"     % (ohN , vfatN)) , 25)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_BIAS_PRE_VREF"       % (ohN , vfatN)) , 86)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_BIAS_SH_I_BFCAS"     % (ohN , vfatN)) , 250)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_BIAS_SH_I_BDIFF"     % (ohN , vfatN)) , 150)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_BIAS_SH_I_BFAMP"     % (ohN , vfatN)) , 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_BIAS_SD_I_BDIFF"     % (ohN , vfatN)) , 255)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_BIAS_SD_I_BSF"       % (ohN , vfatN)) , 15)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_BIAS_SD_I_BFCAS"     % (ohN , vfatN)) , 255)
    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_RUN"%(ohN,vfatN)), 1)

    #unmask and enable calpulsing on the given channels
    if channel_list is not None:
        for channel in channel_list:
            write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.VFAT_CHANNELS.CHANNEL%i"%(ohN,vfatN,channel)), 0x8000)


def lpgbt_vfat_sbit(system, vfat, channel_list, nl1a, runtime, l1a_bxgap):
    print ("LPGBT VFAT S-Bit Test\n")
    
    # Enable the generator
    vfat_oh_link_reset()
    sleep(0.1)
    write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.VFAT3.SC_ONLY_MODE"), 1)
    
    # Configure TTC generator
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.ENABLE"), 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_CALPULSE_TO_L1A_GAP"), 50) # 50 BX between Calpulse and L1A
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_GAP"), l1a_bxgap)
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_COUNT"), nl1a)

    lpgbt, oh_select, gbt_select, elink = vfat_to_oh_gbt_elink(vfat)
    print ("Testing VFAT#: %02d\n" %(vfat))

    write_backend_reg(get_rwreg_node("GEM_AMC.TRIGGER.SBIT_MONITOR.OH_SELECT"), oh_select)

    #write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.FPGA.TRIG.CTRL.VFAT_MASK" % oh_select), vfatMask)

    #for i in range(12):
    #    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.FPGA.TRIG.CTRL.TU_MASK.VFAT%i_TU_MASK" % (oh_select, i)), 0)

    # configure all vfats on the OH with default configuration
    #for i in range(6):
    #    syncErrCnt = read_backend_reg(get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.SYNC_ERR_CNT" % (oh_select, i)))
    #    if syncErrCnt > 0:
    #        print(Colors.YELLOW + "Skipping VFAT%d because it seems dead (sync err cnt = %d)" % (i, syncErrCnt) + Colors.ENDC)
    #    else:
    #        print("Configuring VFAT %d with default configuration" % i)
    #    configureVfatForPulsing(i, oh_select, -1)
    #print ("")
    
    # configure the pulsing VFAT
    print("Configuring VFAT %d for pulsing on channels:" % (vfat))
    print (channel_list)
    configureVfatForPulsing(vfat-6*oh_select, oh_select, channel_list)

    # Reading S-bit counter
    if nl1a != 0:
        print ("\nReading S-bit counter for %d L1A cycles\n" % (nl1a))
    else:
        print ("\nReading S-bit counter for %.2f minutes\n" %(runtime))
    s_bit_counter = 0
    cyclic_running_node = get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_RUNNING")
    counter_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SBIT_COUNT_ME0")
    l1a_node = get_rwreg_node("GEM_AMC.TTC.CMD_COUNTERS.L1A")
    calpulse_node = get_rwreg_node("GEM_AMC.TTC.CMD_COUNTERS.CALPULSE")

    # Start the cyclic generator
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_START"), 1)

    cyclic_running = read_backend_reg(cyclic_running_node)
    t0 = time()
    time_prev = t0
    if nl1a != 0:
        while cyclic_running:
            cyclic_running = read_backend_reg(cyclic_running_node)
            time_passed = (time()-time_prev)/60.0
            if time_passed >= 1:
                s_bit_counter = read_backend_reg(counter_node)
                l1a_counter = read_backend_reg(l1a_node)
                calpulse_counter = read_backend_reg(calpulse_node)
                print ("Time passed: %.2f minutes, L1A counter = %d,  Calpulse counter = %d,  S-bit counter = %d" % ((time()-t0)/60.0, l1a_counter, calpulse_counter, s_bit_counter))
                time_prev = time()
    else:
        while ((time()-t0)/60.0) < runtime:
            time_passed = (time()-time_prev)/60.0
            if time_passed >= 1:
                s_bit_counter = read_backend_reg(counter_node)
                l1a_counter = read_backend_reg(l1a_node)
                calpulse_counter = read_backend_reg(calpulse_node)
                print ("Time passed: %.2f minutes, L1A counter = %d,  Calpulse counter = %d,  S-bit counter = %d" % ((time()-t0)/60.0, l1a_counter, calpulse_counter, s_bit_counter))
                time_prev = time()

    # Stop the cyclic generator
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)

    total_time = time() - t0
    print ("L1A and Calpulsing cycle completed in %.2f minutes \n"%(total_time/60.0))
    s_bit_counter = read_backend_reg(counter_node)
    l1a_counter = read_backend_reg(l1a_node)
    calpulse_counter = read_backend_reg(calpulse_node)

    write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.VFAT3.SC_ONLY_MODE"), 0)

    l1a_rate = 1e9/(l1a_bxgap * 25) # in Hz
    s_bit_expected = 0
    if system != "dryrun":
        s_bit_expected = len(channel_list) * l1a_counter
        print ("Time: %.2f minutes,  L1A rate: %.2f kHz, Nr. of L1A's: %d,  Nr. of Calpulses: %d,  S-bits expected: %d,  S-bit counter: %d" %(total_time/60.0, l1a_rate/1000.0, l1a_counter, calpulse_counter, s_bit_expected, s_bit_counter))
    else:
        if nl1a != 0:
            s_bit_expected = len(channel_list) * nl1a
            print ("Number of L1A cycles: %d,  S-bits expected: %d,  S-bit counter: %d" %(nl1a, s_bit_expected, s_bit_counter))
        else:
            s_bit_expected = len(channel_list) * l1a_rate * runtime
            print ("Time: %.2f minutes,  L1A rate: %.2f kHz,  Nr. of L1A cycles: %.2f,  S-bits expected: %d,  S-bit counter: %d" %(runtime, l1a_rate/1000.0, l1a_rate * runtime, s_bit_expected, s_bit_counter))

    n_err = s_bit_expected - s_bit_counter
    ber = float(n_err)/s_bit_expected
    ber_ul = 1.0/s_bit_expected
    if ber==0:
        print (Colors.GREEN + "Errors = %d,  Bit Error Ratio (BER) < "%(n_err) + "{:.2e}".format(ber_ul) + Colors.ENDC)
    else:
        print (Colors.YELLOW + "Errors = %d,  Bit Error Ratio (BER) = "%(n_err) + "{:.2e}".format(ber) + Colors.ENDC)

    print ("\nS-bit testing done\n")

if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='LpGBT VFAT S-Bit Test')
    parser.add_argument("-s", "--system", action="store", dest="system", help="system = backend or dryrun")
    #parser.add_argument("-l", "--lpgbt", action="store", dest="lpgbt", help="lpgbt = boss or sub")
    parser.add_argument("-v", "--vfat", action="store", dest="vfat", help="vfat = VFAT number (0-11)")
    parser.add_argument("-c", "--channels", action="store", dest="channels", nargs='+', help="channels = list of channels for chosen VFAT (0-127) or all")
    #parser.add_argument("-o", "--ohid", action="store", dest="ohid", help="ohid = 0-7 (only needed for backend)")
    #parser.add_argument("-g", "--gbtid", action="store", dest="gbtid", help="gbtid = 0, 1 (only needed for backend)")
    parser.add_argument("-n", "--nl1a", action="store", dest="nl1a", help="nl1a = fixed number of L1A cycles")
    parser.add_argument("-t", "--time", action="store", dest="time", help="time = time for which to run the S-bit testing (in minutes)")
    parser.add_argument("-b", "--bxgap", action="store", dest="bxgap", default="500", help="bxgap = Nr. of BX between two L1A's (default = 500 i.e. 12.5 us)")
    parser.add_argument("-a", "--addr", action="store_true", dest="addr", help="if plugin card addressing needs should be enabled")
    args = parser.parse_args()

    if args.system == "chc":
        #print ("Using Rpi CHeeseCake for S-bit test")
        print (Colors.YELLOW + "Only Backend or dryrun supported" + Colors.ENDC)
        sys.exit()
    elif args.system == "backend":
        print ("Using Backend for S-bit test")
        #print ("Only chc (Rpi Cheesecake) or dryrun supported at the moment")
        #sys.exit()
    elif args.system == "dongle":
        #print ("Using USB Dongle for S-bit test")
        print (Colors.YELLOW + "Only Backend or dryrun supported" + Colors.ENDC)
        sys.exit()
    elif args.system == "dryrun":
        print ("Dry Run - not actually running vfat bert")
    else:
        print (Colors.YELLOW + "Only valid options: backend, dryrun" + Colors.ENDC)
        sys.exit()

    if args.vfat is None:
        print (Colors.YELLOW + "Enter VFAT number" + Colors.ENDC)
        sys.exit()
    vfat = int(args.vfat)
    if vfat not in range(0,12):
        print (Colors.YELLOW + "Invalid VFAT number, only allowed 0-11" + Colors.ENDC)
        sys.exit()
        
    if args.channels is None:
        print (Colors.YELLOW + "Enter Channel numbers" + Colors.ENDC)
        sys.exit()
    channel_list = []
    if args.channels == ["all"]:
        for i in range(0,128):
            channel_list.append(i)
    else:
        for c in args.channels:
            c_int = int(c)
            if c_int not in range(0,128):
                print (Colors.YELLOW + "Invalid Channel number, only allowed 0-127" + Colors.ENDC)
                sys.exit()
            channel_list.append(c_int)

    nl1a = 0
    if args.nl1a is not None:
        nl1a = int(args.nl1a)
        if args.time is not None:
            print (Colors.YELLOW + "Cannot give both time and number of L1A cycles" + Colors.ENDC)
            sys.exit()
    runtime = 0
    if args.time is not None:
        runtime = float(args.time)
        if args.nl1a is not None:
            if args.time is not None:
                print (Colors.YELLOW + "Cannot give both tiime and number of L1A cycles" + Colors.ENDC)
                sys.exit()
    if nl1a==0 and runtime==0:
        print (Colors.YELLOW + "Enter either runtime or number of L1A cycles" + Colors.ENDC)
        sys.exit()

    l1a_bxgap = int(args.bxgap)
    l1a_timegap = l1a_bxgap * 25 * 0.001 # in microseconds
    if l1a_bxgap<25:
        print (Colors.YELLOW + "Gap between L1A's should be at least 25 BX to read out enitre DAQ data packets" + Colors.ENDC)
        sys.exit()
    else:
        print ("Gap between consecutive L1A or CalPulses = %d BX = %.2f us" %(l1a_bxgap, l1a_timegap))

    if args.addr:
        print ("Enabling VFAT addressing for plugin cards")
        write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.VFAT3.USE_VFAT_ADDRESSING"), 1)

    # Parsing Registers XML File
    print("Parsing xml file...")
    parseXML()
    print("Parsing complete...")

    # Initialization (for CHeeseCake: reset and config_select)
    rw_initialize(args.system)
    print("Initialization Done\n")
    
    # Running Phase Scan
    try:
        lpgbt_vfat_sbit(args.system, vfat, channel_list, nl1a, runtime, l1a_bxgap)
    except KeyboardInterrupt:
        print (Colors.RED + "Keyboard Interrupt encountered" + Colors.ENDC)
        rw_terminate()
    except EOFError:
        print (Colors.RED + "\nEOF Error" + Colors.ENDC)
        rw_terminate()

    # Termination
    rw_terminate()




