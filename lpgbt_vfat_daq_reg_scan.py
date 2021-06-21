from rw_reg_lpgbt import *
from time import sleep, time
import datetime
import sys
import argparse
import random
from lpgbt_vfat_config import configureVfat, enableVfatchannel

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

# Register to read/write
vfat_registers = {
        "HW_ID": "r",
        "HW_ID_VER": "r",
        "TEST_REG": "rw",
        "HW_CHIP_ID": "r"
}

def vfat_to_oh_gbt_elink(vfat):
    lpgbt = VFAT_TO_ELINK[vfat][0]
    ohid  = VFAT_TO_ELINK[vfat][1]
    gbtid = VFAT_TO_ELINK[vfat][2]
    elink = VFAT_TO_ELINK[vfat][3]
    return lpgbt, ohid, gbtid, elink

def lpgbt_vfat_reg_scan(system, dac, vfat_list, channel_list, lower, upper, step, nl1a, l1a_bxgap):
    print ("Performing Register Scan for: %s\n"%dac)
    if not os.path.exists("daq_reg_scan_results"):
        os.makedirs("daq_reg_scan_results")
    now = str(datetime.datetime.now())[:16]
    now = now.replace(":", "_")
    now = now.replace(" ", "_")
    foldername = "daq_reg_scan_results/"
    filename = foldername + "vfat_reg_scan_" + dac + "_" + now + ".txt"
    file_out = open(filename,"w+")
    file_out.write("vfat    channel    register    fired    events\n")

    vfat_oh_link_reset()
    global_reset()
    sleep(0.1)

    daq_data = {}
    # Check ready and get nodes
    for vfat in vfat_list:
        lpgbt, oh_select, gbt_select, elink = vfat_to_oh_gbt_elink(vfat)
        check_lpgbt_link_ready(oh_select, gbt_select)

        print("Configuring VFAT %d" % (vfat))
        configureVfat(1, vfat, oh_select, 0)
        for channel in channel_list:
            enableVfatchannel(vfat, oh_select, channel, 1, 0) # mask all channels and disable calpulsing

        link_good_node = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.LINK_GOOD" % (oh_select, vfat))
        sync_error_node = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.SYNC_ERR_CNT" % (oh_select, vfat))
        link_good = read_backend_reg(link_good_node)
        sync_err = read_backend_reg(sync_error_node)
        if system!="dryrun" and (link_good == 0 or sync_err > 0):
            print (Colors.RED + "Link is bad for VFAT# %02d"%(vfat) + Colors.ENDC)
            rw_terminate()

        daq_data[vfat] = {}
        for channel in channel_list:
            daq_data[vfat][channel] = {}
            for reg in range(lower,upper+1,step):
                daq_data[vfat][channel][reg] = {}
                daq_data[vfat][channel][reg]["events"] = -9999
                daq_data[vfat][channel][reg]["fired"] = -9999

    # Configure TTC generator
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.SINGLE_HARD_RESET"), 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.ENABLE"), 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_GAP"), l1a_bxgap)
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_COUNT"), nl1a)
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_CALPULSE_TO_L1A_GAP"), 50) # 50 BX between Calpulse and L1A

    # Setup the DAQ monitor
    write_backend_reg(get_rwreg_node("GEM_AMC.GEM_TESTS.VFAT_DAQ_MONITOR.CTRL.ENABLE"), 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.GEM_TESTS.VFAT_DAQ_MONITOR.CTRL.VFAT_CHANNEL_GLOBAL_OR"), 0)

    cyclic_running_node = get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_RUNNING")
    l1a_node = get_rwreg_node("GEM_AMC.TTC.CMD_COUNTERS.L1A")
    calpulse_node = get_rwreg_node("GEM_AMC.TTC.CMD_COUNTERS.CALPULSE")

    print ("\nRunning DAC Scans for %.2e L1A cycles for VFATs:" % (nl1a))
    print (vfat_list)
    print ("")

    # Looping over channels
    for channel in channel_list:
        print ("Channel: %d"%channel)
        for vfat in vfat_list:
            lpgbt, oh_select, gbt_select, elink = vfat_to_oh_gbt_elink(vfat)
            write_backend_reg(get_rwreg_node("GEM_AMC.GEM_TESTS.VFAT_DAQ_MONITOR.CTRL.OH_SELECT"), oh_select)
            enableVfatchannel(vfat, oh_select, channel, 0, 1) # unmask channel and enable calpulsing
        write_backend_reg(get_rwreg_node("GEM_AMC.GEM_TESTS.VFAT_DAQ_MONITOR.CTRL.VFAT_CHANNEL_SELECT"), channel)
        
        # Looping over charge
        for reg in range(lower,upper+1,step):
            print ("    %s: %d"%(dac,reg))
       	    for vfat in vfat_list:
       	        lpgbt, oh_select, gbt_select, elink = vfat_to_oh_gbt_elink(vfat)
                write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%d.%s"%(oh_select, vfat, dac)), reg)
           
            write_backend_reg(get_rwreg_node("GEM_AMC.GEM_TESTS.VFAT_DAQ_MONITOR.CTRL.RESET"), 1)
            write_backend_reg(get_rwreg_node("GEM_AMC.GEM_TESTS.VFAT_DAQ_MONITOR.CTRL.ENABLE"), 1)

		    # Start the cyclic generator
            l1a_counter_initial = read_backend_reg(l1a_node)
            calpulse_counter_initial = read_backend_reg(calpulse_node)
            write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.ENABLE"), 1)
            write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_START"), 1)
            cyclic_running = 1
            while (cyclic_running):
                cyclic_running = read_backend_reg(cyclic_running_node)
            # Stop the cyclic generator
            write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)
            l1a_counter = read_backend_reg(l1a_node) - l1a_counter_initial
            calpulse_counter = read_backend_reg(calpulse_node) - calpulse_counter_initial
            write_backend_reg(get_rwreg_node("GEM_AMC.GEM_TESTS.VFAT_DAQ_MONITOR.CTRL.ENABLE"), 0)

            # Looping over VFATs
            for vfat in vfat_list:
                lpgbt, oh_select, gbt_select, elink = vfat_to_oh_gbt_elink(vfat)
                daq_data[vfat][channel][reg]["events"] = read_backend_reg(get_rwreg_node("GEM_AMC.GEM_TESTS.VFAT_DAQ_MONITOR.VFAT%d.GOOD_EVENTS_COUNT"%(vfat)))
                daq_data[vfat][channel][reg]["fired"] = read_backend_reg(get_rwreg_node("GEM_AMC.GEM_TESTS.VFAT_DAQ_MONITOR.VFAT%d.CHANNEL_FIRE_COUNT"%(vfat)))
            # End of VFAT loop
        # End of charge loop
        
        for vfat in vfat_list:
            lpgbt, oh_select, gbt_select, elink = vfat_to_oh_gbt_elink(vfat)
            enableVfatchannel(vfat, oh_select, channel, 1, 0) # mask channel and disable calpulsing
    # End of channel loop
    print ("")

    # Disable channels on VFATs
    for vfat in vfat_list:
        lpgbt, oh_select, gbt_select, elink = vfat_to_oh_gbt_elink(vfat)
        enable_channel = 0
        print("Unconfiguring VFAT %d" % (vfat))
        for channel in channel_list:
            enableVfatchannel(vfat, oh_select, channel, 0, 0) # disable calpulsing on all channels for this VFAT
        configureVfat(0, vfat, oh_select, 0)

    # Writing Results
    for vfat in vfat_list:
        for channel in channel_list:
            for reg in range(0,256,1):
                if reg not in daq_data[vfat][channel]:
                    continue
                file_out.write("%d    %d    %d    %d    %d\n"%(vfat, channel, reg, daq_data[vfat][channel][reg]["fired"], daq_data[vfat][channel][reg]["events"]))

    print ("\n")
    file_out.close()
if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='LpGBT VFAT Register Scan')
    parser.add_argument("-s", "--system", action="store", dest="system", help="system = backend or dryrun")
    #parser.add_argument("-l", "--lpgbt", action="store", dest="lpgbt", help="lpgbt = boss or sub")
    parser.add_argument("-v", "--vfats", action="store", dest="vfats", nargs='+', help="vfats = list of VFATs (0-11) - only ones belonging to the same OH")
    #parser.add_argument("-o", "--ohid", action="store", dest="ohid", help="ohid = 0-7 (only needed for backend)")
    #parser.add_argument("-g", "--gbtid", action="store", dest="gbtid", help="gbtid = 0, 1 (only needed for backend)")
    parser.add_argument("-c", "--channels", action="store", nargs='+', dest="channels", help="channels = list of channels (default: 0-127)")
    parser.add_argument("-r", "--regs", action="store", nargs='+', dest="regs", help="Registers to scan")
    parser.add_argument("-ll", "--lower", action="store", dest="lower", default="0", help="lower = Lower limit for DAC scan (default=0)")
    parser.add_argument("-ul", "--upper", action="store", dest="upper", default="255", help="upper = Upper limit for DAC scan (default=255)")
    parser.add_argument("-t", "--step", action="store", dest="step", default="1", help="step = Step size for DAC scan (default=1)")
    parser.add_argument("-n", "--nl1a", action="store", dest="nl1a", help="nl1a = fixed number of L1A cycles")
    parser.add_argument("-b", "--bxgap", action="store", dest="bxgap", default="500", help="bxgap = Nr. of BX between two L1A's (default = 500 i.e. 12.5 us)")
    parser.add_argument("-a", "--addr", action="store_true", dest="addr", help="if plugin card addressing needs should be enabled")
    args = parser.parse_args()

    if args.system == "chc":
        #print ("Using Rpi CHeeseCake for configuration")
        print (Colors.YELLOW + "Only Backend or dryrun supported" + Colors.ENDC)
        sys.exit()
    elif args.system == "backend":
        print ("Using Backend for configuration")
        #print ("Only chc (Rpi Cheesecake) or dryrun supported at the moment")
        #sys.exit()
    elif args.system == "dongle":
        #print ("Using USB Dongle for configuration")
        print (Colors.YELLOW + "Only Backend or dryrun supported" + Colors.ENDC)
        sys.exit()
    elif args.system == "dryrun":
        print ("Dry Run - not actually running vfat bert")
    else:
        print (Colors.YELLOW + "Only valid options: backend, dryrun" + Colors.ENDC)
        sys.exit()

    if args.regs is None:
        print(Colors.YELLOW + "Need list of Registers to scan" + Colors.ENDC)
        sys.exit()

    if args.vfats is None:
        print (Colors.YELLOW + "Enter VFAT numbers" + Colors.ENDC)
        sys.exit()
    vfat_list = []
    for v in args.vfats:
        v_int = int(v)
        if v_int not in range(0,12):
            print (Colors.YELLOW + "Invalid VFAT number, only allowed 0-11" + Colors.ENDC)
            sys.exit()
        vfat_list.append(v_int)
        
    oh_match = -9999
    for vfat in vfat_list:
        lpgbt, oh_select, gbt_select, elink = vfat_to_oh_gbt_elink(vfat)
        if oh_match == -9999:
            oh_match = oh_select
        else:
            if oh_match != oh_select:
                print (Colors.YELLOW + "Only VFATs belonging to the same OH allowed" + Colors.ENDC)
                sys.exit()

    channel_list = []
    if args.channels is None:
        channel_list = range(0,128)
    else:
        for c in args.channels:
            c_int = int(c)
            if c_int not in range(0,128):
                print (Colors.YELLOW + "Invalid channel, only allowed 0-127" + Colors.ENDC)
                sys.exit()
            channel_list.append(c_int)
        
    lower = int(args.lower)
    upper = int(args.upper)
    if lower not in range(0,256):
        print (Colors.YELLOW + "Lower limit can only be between 0 and 255" + Colors.ENDC)
        sys.exit()
    if upper not in range(0,256):
        print (Colors.YELLOW + "Upper limit can only be between 0 and 255" + Colors.ENDC)
        sys.exit()
    if lower>upper:
        print (Colors.YELLOW + "Upper limit has to be >= Lower limit" + Colors.ENDC)
        sys.exit()
        
    step = int(args.step)
    if step not in range(1,257):
        print (Colors.YELLOW + "Step size can only be between 1 and 256" + Colors.ENDC)
        sys.exit()

    nl1a = 0
    if args.nl1a is not None:
        nl1a = int(args.nl1a)
        if nl1a > (2**24 - 1):
            print (Colors.YELLOW + "Number of L1A cycles can be maximum 1.68e7. Using time option for longer tests" + Colors.ENDC)
            sys.exit()
    if nl1a==0:
        print (Colors.YELLOW + "Enter number of L1A cycles" + Colors.ENDC)
        sys.exit()

    l1a_bxgap = int(args.bxgap)
    l1a_timegap = l1a_bxgap * 25 * 0.001 # in microseconds
    if l1a_bxgap<25:
        print (Colors.YELLOW + "Gap between L1A's should be at least 25 BX to read out enitre DAQ data packets" + Colors.ENDC)
        sys.exit()
    else:
        print ("Gap between consecutive L1A or CalPulses = %d BX = %.2f us" %(l1a_bxgap, l1a_timegap))
        
    # Parsing Registers XML File
    print("Parsing xml file...")
    parseXML()
    print("Parsing complete...")

    # Initialization (for CHeeseCake: reset and config_select)
    rw_initialize(args.system)
    print("Initialization Done\n")

    if args.addr:
        print ("Enabling VFAT addressing for plugin cards")
        write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.VFAT3.USE_VFAT_ADDRESSING"), 1)
    
    # Running Phase Scan
    try:
        for reg in args.regs:
            lpgbt_vfat_reg_scan(args.system, reg, vfat_list, channel_list, lower, upper, step, nl1a, l1a_bxgap)
    except KeyboardInterrupt:
        print (Colors.RED + "Keyboard Interrupt encountered" + Colors.ENDC)
        rw_terminate()
    except EOFError:
        print (Colors.RED + "\nEOF Error" + Colors.ENDC)
        rw_terminate()

    # Termination
    rw_terminate()




