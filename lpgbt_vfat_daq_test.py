from rw_reg_lpgbt import *
from time import sleep, time
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

def lpgbt_vfat_bert(system, vfat_list, nl1a, runtime, l1a_bxgap, calpulse):
    file_out = open("vfat_daq_test_output.txt", "w+")

    if nl1a!=0:
        print ("LPGBT VFAT Bit Error Ratio Test with %.2e L1A's\n" % (nl1a))
        file_out.write("LPGBT VFAT Bit Error Ratio Test with %.2e L1A's\n\n" % (nl1a))
    elif runtime!=0:
        print ("LPGBT VFAT Bit Error Ratio Test for %.2f minutes\n" % (runtime))
        file_out.write("LPGBT VFAT Bit Error Ratio Test for %.2f minutes\n\n" % (runtime))
    errors = {}
    error_rates = {}

    vfat_oh_link_reset()
    global_reset()
    sleep(0.1)

    link_good_node = {}
    sync_error_node = {}
    daq_event_count_node = {}
    daq_crc_error_node = {}
    daq_event_count_initial = 12*[0]
    daq_crc_error_count_initial = 12*[0]
    daq_event_count_final = 12*[0]
    daq_crc_error_count_final = 12*[0]
    daq_event_count_diff = 12*[0]
    daq_crc_error_count_diff = 12*[0]

    l1a_rate = 1e9/(l1a_bxgap * 25) # in Hz
    efficiency = 1
    if l1a_rate > 1e6 * 0.5:
        efficiency = 0.977

    # Check ready and get nodes
    for vfat in vfat_list:
        lpgbt, oh_select, gbt_select, elink = vfat_to_oh_gbt_elink(vfat)
        check_lpgbt_link_ready(oh_select, gbt_select)

        print("Configuring VFAT %d" % (vfat))
        file_out.write("Configuring VFAT %d\n" % (vfat))
        configureVfat(1, vfat-6*oh_select, oh_select, 0)
        if calpulse:
            enableVfatchannel(vfat-6*oh_select, oh_select, 0, 0, 1) # enable calpulsing on channel 0 for this VFAT

        link_good_node[vfat] = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.LINK_GOOD" % (oh_select, vfat-6*oh_select))
        sync_error_node[vfat] = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.SYNC_ERR_CNT" % (oh_select, vfat-6*oh_select))
        link_good = read_backend_reg(link_good_node[vfat])
        sync_err = read_backend_reg(sync_error_node[vfat])
        if system!="dryrun" and (link_good == 0 or sync_err > 0):
            print (Colors.RED + "Link is bad for VFAT# %02d"%(vfat) + Colors.ENDC)
            rw_terminate()
        daq_event_count_node[vfat] = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.DAQ_EVENT_CNT" % (oh_select, vfat-6*oh_select))
        daq_crc_error_node[vfat] = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.DAQ_CRC_ERROR_CNT" % (oh_select, vfat-6*oh_select))
        daq_event_count_initial[vfat] = read_backend_reg(daq_event_count_node[vfat])
        daq_crc_error_count_initial[vfat] = read_backend_reg(daq_crc_error_node[vfat])

    # Configure TTC generator
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.ENABLE"), 1)
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_GAP"), l1a_bxgap)
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_COUNT"), nl1a)

    if calpulse:
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_CALPULSE_TO_L1A_GAP"), 30) # 30 BX between Calpulse and L1A
    else:
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_CALPULSE_TO_L1A_GAP"), 0) # Disable Calpulsing

    if nl1a != 0:
        print ("\nRunning for %.2e L1A cycles for VFATs:" % (nl1a))
        file_out.write("\nRunning for %.2e L1A cycles for VFATs:\n" % (nl1a))
    else:
        print ("\nRunning for %f minutes for VFATs:" %(runtime))
        file_out.write("\nRunning for %f minutes for VFATs:\n" %(runtime))
    print (vfat_list)
    for vfat in vfat_list:
        file_out.write(str(vfat) + "  ")
    file_out.write("\n")
    print ("")
    file_out.write("\n")
    cyclic_running_node = get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_RUNNING")
    l1a_node = get_rwreg_node("GEM_AMC.TTC.CMD_COUNTERS.L1A")
    calpulse_node = get_rwreg_node("GEM_AMC.TTC.CMD_COUNTERS.CALPULSE")
    l1a_counter_initial = read_backend_reg(l1a_node)
    calpulse_counter_initial = read_backend_reg(calpulse_node)

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
                l1a_counter = read_backend_reg(l1a_node) - l1a_counter_initial
                calpulse_counter = read_backend_reg(calpulse_node) - calpulse_counter_initial
                expected_l1a = int(l1a_rate * (time()-t0) * efficiency)
                nl1a_reg_cycles = int(expected_l1a/(2**32))
                real_l1a_counter = nl1a_reg_cycles*(2**32) + l1a_counter
                if calpulse:
                    real_calpulse_counter = nl1a_reg_cycles*(2**32) + calpulse_counter
                else:
                    real_calpulse_counter = calpulse_counter
                #daq_event_count_temp = read_backend_reg(daq_event_count_node[vfat]) - daq_event_count_initial[vfat]
                daq_event_count_temp = real_l1a_counter # since DAQ_EVENT_CNT is a 8-bit rolling counter
                print ("Time passed: %.2f minutes, L1A counter = %.2e,  Calpulse counter = %.2e, DAQ Events = %.2e" % ((time()-t0)/60.0, real_l1a_counter, real_calpulse_counter, daq_event_count_temp))
                file_out.write("Time passed: %.2f minutes, L1A counter = %.2e,  Calpulse counter = %.2e, DAQ Events = %.2e" % ((time()-t0)/60.0, real_l1a_counter, real_calpulse_counter, daq_event_count_temp))
                vfat_results_string = ""
                for vfat in vfat_list:
                    daq_error_count_temp = read_backend_reg(daq_crc_error_node[vfat]) - daq_crc_error_count_initial[vfat]
                    vfat_results_string += "VFAT %02d DAQ Errors: %d, "%(vfat, daq_error_count_temp)
                print (vfat_results_string + "\n")
                file_out.write(vfat_results_string + "\n\n")
                time_prev = time()
    else:
        while ((time()-t0)/60.0) < runtime:
            time_passed = (time()-time_prev)/60.0
            if time_passed >= 1:
                l1a_counter = read_backend_reg(l1a_node) - l1a_counter_initial
                calpulse_counter = read_backend_reg(calpulse_node) - calpulse_counter_initial
                expected_l1a = int(l1a_rate * (time()-t0) * efficiency)
                nl1a_reg_cycles = int(expected_l1a/(2**32))
                real_l1a_counter = nl1a_reg_cycles*(2**32) + l1a_counter
                if calpulse:
                    real_calpulse_counter = nl1a_reg_cycles*(2**32) + calpulse_counter
                else:
                    real_calpulse_counter = calpulse_counter
                #daq_event_count_temp = read_backend_reg(daq_event_count_node[vfat]) - daq_event_count_initial[vfat]
                daq_event_count_temp = real_l1a_counter # since DAQ_EVENT_CNT is a 8-bit rolling counter
                print ("Time passed: %.2f minutes, L1A counter = %.2e,  Calpulse counter = %.2e, DAQ Events = %.2e" % ((time()-t0)/60.0, real_l1a_counter, real_calpulse_counter, daq_event_count_temp))
                file_out.write("Time passed: %.2f minutes, L1A counter = %.2e,  Calpulse counter = %.2e, DAQ Events = %.2e\n" % ((time()-t0)/60.0, real_l1a_counter, real_calpulse_counter, daq_event_count_temp))
                vfat_results_string = ""
                for vfat in vfat_list:
                    daq_error_count_temp = read_backend_reg(daq_crc_error_node[vfat]) - daq_crc_error_count_initial[vfat]
                    vfat_results_string += "VFAT %02d DAQ Errors: %d, "%(vfat, daq_error_count_temp)
                print (vfat_results_string + "\n")
                file_out.write(vfat_results_string + "\n\n")
                time_prev = time()

    # Stop the cyclic generator
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)

    print ("")
    file_out.write("\n")
    total_time = time() - t0
    print ("L1A and Calpulsing cycle completed in %.2f seconds (%.2f minutes) \n"%(total_time, total_time/60.0))
    file_out.write("L1A and Calpulsing cycle completed in %.2f seconds (%.2f minutes) \n\n"%(total_time, total_time/60.0))
    l1a_counter = read_backend_reg(l1a_node) - l1a_counter_initial
    calpulse_counter = read_backend_reg(calpulse_node) - calpulse_counter_initial

    print ("Error test results for DAQ elinks\n")
    file_out.write("Error test results for DAQ elinks\n\n")
    for vfat in vfat_list:
        link_good = read_backend_reg(link_good_node[vfat])
        sync_err = read_backend_reg(sync_error_node[vfat])
        if link_good == 1:
            print (Colors.GREEN + "VFAT#: %02d, link is GOOD"%(vfat) + Colors.ENDC)
            file_out.write("VFAT#: %02d, link is GOOD\n"%(vfat))
        else:
            print (Colors.RED + "VFAT#: %02d, link is BAD"%(vfat) + Colors.ENDC)
            file_out.write("VFAT#: %02d, link is BAD\n"%(vfat))
        if sync_err==0:
            print (Colors.GREEN + "VFAT#: %02d, nr. of sync errors: %d"%(vfat, sync_err) + Colors.ENDC)
            file_out.write("VFAT#: %02d, nr. of sync errors: %d\n"%(vfat, sync_err))
        else:
            print (Colors.RED + "VFAT#: %02d, nr. of sync errors: %d"%(vfat, sync_err) + Colors.ENDC)
            file_out.write("VFAT#: %02d, nr. of sync errors: %d\n"%(vfat, sync_err))

        daq_event_count_final[vfat] = read_backend_reg(daq_event_count_node[vfat])
        daq_crc_error_count_final[vfat] = read_backend_reg(daq_crc_error_node[vfat])
        daq_event_count_diff[vfat] = daq_event_count_final[vfat] - daq_event_count_initial[vfat]
        daq_crc_error_count_diff[vfat] = daq_crc_error_count_final[vfat] - daq_crc_error_count_initial[vfat]

        expected_l1a = 0
        if nl1a != 0:
            expected_l1a = nl1a
        else:
            expected_l1a = int(l1a_rate * runtime * 60 * efficiency)
        real_l1a_counter = 0
        real_calpulse_counter = 0

        if system != "dryrun":
            nl1a_reg_cycles = int(expected_l1a/(2**32))
            real_l1a_counter = nl1a_reg_cycles*(2**32) + l1a_counter
            if calpulse:
                real_calpulse_counter = nl1a_reg_cycles*(2**32) + calpulse_counter
            else:
                real_calpulse_counter = calpulse_counter
            if daq_event_count_diff[vfat] != real_l1a_counter%256:
                print (Colors.YELLOW + "Mismatch between DAQ_EVENT_CNT and L1A counter: %d"%(daq_event_count_diff[vfat] - real_l1a_counter%256) + Colors.ENDC)
                file_out.write("Mismatch between DAQ_EVENT_CNT and L1A counter: %d\n"%(daq_event_count_diff[vfat] - real_l1a_counter%256))
            daq_event_count_diff[vfat] = real_l1a_counter # since DAQ_EVENT_CNT is a 8-bit rolling counter
        else:
            if nl1a != 0:
                daq_event_count_diff[vfat] = nl1a
                l1a_counter = nl1a
                real_l1a_counter = nl1a
                if calpulse:
                    calpulse_counter = nl1a
                    real_calpulse_counter = nl1a
                else:
                    calpulse_counter = 0
            else:
                daq_event_count_diff[vfat] = expected_l1a
                l1a_counter = expected_l1a
                real_l1a_counter = expected_l1a
                if calpulse:
                    calpulse_counter = expected_l1a
                    real_calpulse_counter = expected_l1a
                else:
                    calpulse_counter = 0
        print ("VFAT#: %02d, Time: %.2f minutes,  L1A rate: %.2f kHz, Expected L1A's (effi=%.3f): %.2e, Nr. of L1A's: %.2e,  Nr. of Calpulses: %.2e  \nDAQ Events: %.2e,  DAQ CRC Errors: %d" %(vfat, total_time/60.0, l1a_rate/1000.0, efficiency, expected_l1a, real_l1a_counter, real_calpulse_counter, daq_event_count_diff[vfat], daq_crc_error_count_diff[vfat]))
        file_out.write("VFAT#: %02d, Time: %.2f minutes,  L1A rate: %.2f kHz, Expected L1A's (effi=%.3f): %.2e, Nr. of L1A's: %.2e,  Nr. of Calpulses: %.2e  \nDAQ Events: %.2e,  DAQ CRC Errors: %d\n" %(vfat, total_time/60.0, l1a_rate/1000.0, efficiency, expected_l1a, real_l1a_counter, real_calpulse_counter, daq_event_count_diff[vfat], daq_crc_error_count_diff[vfat]))

        daq_data_packet_size = 176 # 176 bits
        if daq_event_count_diff[vfat]==0:
            ber = 0
        else:
            ber = float(daq_crc_error_count_diff[vfat])/(daq_event_count_diff[vfat] * daq_data_packet_size)
        ber_ul = 1.0/(daq_event_count_diff[vfat] * daq_data_packet_size)
        if ber==0:
            print (Colors.GREEN + "VFAT#: %02d, Errors = %d,  Bit Error Ratio (BER) < "%(vfat, daq_crc_error_count_diff[vfat]) + "{:.2e}".format(ber_ul) + Colors.ENDC)
            file_out.write("VFAT#: %02d, Errors = %d,  Bit Error Ratio (BER) < "%(vfat, daq_crc_error_count_diff[vfat]) + "{:.2e}\n".format(ber_ul))
        else:
            print (Colors.YELLOW + "VFAT#: %02d, Errors = %d,  Bit Error Ratio (BER) = "%(vfat, daq_crc_error_count_diff[vfat]) + "{:.2e}".format(ber) + Colors.ENDC)
            file_out.write("VFAT#: %02d, Errors = %d,  Bit Error Ratio (BER) = "%(vfat, daq_crc_error_count_diff[vfat]) + "{:.2e}\n".format(ber))

            print ("")
            file_out.write("\n")
        print ("")
        file_out.write("\n")

    # Disable channels on VFATs
    for vfat in vfat_list:
        lpgbt, oh_select, gbt_select, elink = vfat_to_oh_gbt_elink(vfat)
        enable_channel = 0
        print("Unconfiguring VFAT %d" % (vfat))
        file_out.write("Unconfiguring VFAT %d\n" % (vfat))
        if calpulse:
            enableVfatchannel(vfat-6*oh_select, oh_select, 0, 0, 0) # disable calpulsing on channel 0 for this VFAT
        configureVfat(0, vfat-6*oh_select, oh_select, 0)

    file_out.close()
if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='LpGBT VFAT DAQ Error Ratio Test')
    parser.add_argument("-s", "--system", action="store", dest="system", help="system = backend or dryrun")
    #parser.add_argument("-l", "--lpgbt", action="store", dest="lpgbt", help="lpgbt = boss or sub")
    parser.add_argument("-v", "--vfats", action="store", dest="vfats", nargs='+', help="vfats = list of VFATs (0-11)")
    #parser.add_argument("-o", "--ohid", action="store", dest="ohid", help="ohid = 0-7 (only needed for backend)")
    #parser.add_argument("-g", "--gbtid", action="store", dest="gbtid", help="gbtid = 0, 1 (only needed for backend)")
    parser.add_argument("-n", "--nl1a", action="store", dest="nl1a", help="nl1a = fixed number of L1A cycles")
    parser.add_argument("-t", "--time", action="store", dest="time", help="time = time (in minutes) to perform the DAQ test")
    parser.add_argument("-b", "--bxgap", action="store", dest="bxgap", default="500", help="bxgap = Nr. of BX between two L1A's (default = 500 i.e. 12.5 us)")
    parser.add_argument("-c", "--calpulse", action="store_true", dest="calpulse", help="if calpulsing for all channels should be enabled")
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

    nl1a = 0
    if args.nl1a is not None:
        nl1a = int(args.nl1a)
        if args.time is not None:
            print (Colors.YELLOW + "Cannot give both time and number of L1A cycles" + Colors.ENDC)
            sys.exit()
        if nl1a > (2**24 - 1):
            print (Colors.YELLOW + "Number of L1A cycles can be maximum 1.68e7. Using time option for longer tests" + Colors.ENDC)
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

    if args.calpulse:
        print ("Calpulsing enabled for all channels for given VFATs")

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
        lpgbt_vfat_bert(args.system, vfat_list, nl1a, runtime, l1a_bxgap, args.calpulse)
    except KeyboardInterrupt:
        print (Colors.RED + "Keyboard Interrupt encountered" + Colors.ENDC)
        rw_terminate()
    except EOFError:
        print (Colors.RED + "\nEOF Error" + Colors.ENDC)
        rw_terminate()

    # Termination
    rw_terminate()




