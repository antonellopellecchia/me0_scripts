from rw_reg_lpgbt import *
from time import sleep, time
import sys
import argparse
import random
import glob
import json
from lpgbt_vfat_config import configureVfat, enableVfatchannel


def lpgbt_vfat_sbit(system, oh_select, vfat, elink_list, channel_list, sbit_list, nl1a, runtime, l1a_bxgap):
    file_out = open("vfat_sbit_test_outtput.txt", "w")
    print ("LPGBT VFAT S-Bit Test\n")
    file_out.write("LPGBT VFAT S-Bit Test\n\n")

    vfat_oh_link_reset()
    global_reset()
    sleep(0.1)
    write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.VFAT3.SC_ONLY_MODE"), 1)

    lpgbt, gbt_select, elink, gpio = vfat_to_gbt_elink_gpio(vfat)
    print ("Testing VFAT#: %02d\n" %(vfat))
    file_out.write("Testing VFAT#: %02d\n\n")
    
    check_lpgbt_link_ready(oh_select, gbt_select)
    link_good = read_backend_reg(get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.LINK_GOOD" % (oh_select, vfat)))
    sync_err = read_backend_reg(get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.SYNC_ERR_CNT" % (oh_select, vfat)))
    if system!="dryrun" and (link_good == 0 or sync_err > 0):
        print (Colors.RED + "Link is bad for VFAT# %02d"%(vfat) + Colors.ENDC)
        rw_terminate()

    # Reset TTC generator
    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)

    # Reading S-bit counter
    if nl1a != 0:
        print ("\nReading S-bit counter for %d L1A cycles\n" % (nl1a))
        file_out.write("\nReading S-bit counter for %d L1A cycles\n\n" % (nl1a))
    else:
        print ("\nReading S-bit counter for %.2f minutes\n" %(runtime))
        file_out.write("\nReading S-bit counter for %.2f minutes\n\n" %(runtime))
    cyclic_running_node = get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_RUNNING")
    l1a_node = get_rwreg_node("GEM_AMC.TTC.CMD_COUNTERS.L1A")
    calpulse_node = get_rwreg_node("GEM_AMC.TTC.CMD_COUNTERS.CALPULSE")

    write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SEL_VFAT_SBIT_ME0"), vfat) # Select VFAT for reading S-bits
    elink_sbit_select_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SEL_ELINK_SBIT_ME0") # Node for selecting Elink to count
    channel_sbit_select_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SEL_SBIT_ME0") # Node for selecting S-bit to count
    elink_sbit_counter_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SBIT0XE_COUNT_ME0") # S-bit counter for elink
    channel_sbit_counter_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SBIT0XS_COUNT_ME0") # S-bit counter for specific channel
    reset_sbit_counter_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.CTRL.SBIT_TEST_RESET")  # To reset all S-bit counters

    elink_sbit_counter = 0
    channel_sbit_counter = 0
    elink_sbit_counter_list = {}
    channel_sbit_counter_list = {}
    l1a_counter_list = {}
    calpulse_counter_list = {}

    l1a_rate = 1e9/(l1a_bxgap * 25) # in Hz
    efficiency = 1
    if l1a_rate > 1e6 * 0.5:
        efficiency = 0.977

    # Configure the pulsing VFAT
    print("Configuring VFAT %02d" % (vfat))
    file_out.write("Configuring VFAT %02d\n" % (vfat))
    configureVfat(1, vfat, oh_select, 0)

    for elink in elink_list:
        print ("Channel List in ELINK# %02d:" %(elink))
        file_out.write("Channel List in ELINK# %02d:\n" %(elink))
        print (channel_list[elink])
        for channel in channel_list[elink]:
            file_out.write(str(channel) + "  ")
        file_out.write("\n")
        print ("Reading Sbit List in ELINK# %02d:" %(elink))
        file_out.write("Reading Sbit List in ELINK# %02d:\n" %(elink))
        print (sbit_list[elink])
        for sbit in sbit_list[elink]:
            file_out.write(str(sbit) + "  ")
        file_out.write("\n")
        print ("")
        file_out.write("\n")

        elink_sbit_counter_list[elink] = {}
        channel_sbit_counter_list[elink]  = {}
        l1a_counter_list[elink]  = {}
        calpulse_counter_list[elink]  = {}

        for channel, sbit_read in zip(channel_list[elink], sbit_list[elink]):
            # Reset L1A, CalPulse and S-bit counters
            global_reset()
            write_backend_reg(reset_sbit_counter_node, 1)

            # Enabling the pulsing channel
            print("Enabling pulsing on channel %02d in ELINK# %02d:" % (channel, elink))
            file_out.write("Enabling pulsing on channel %02d in ELINK# %02d:\n" % (channel, elink))
            for i in range(128):
                enableVfatchannel(vfat, oh_select, i, 1, 0) # mask all channels and disable calpulsing
            enableVfatchannel(vfat, oh_select, channel, 0, 1) # unmask this channel and enable calpulsing

            write_backend_reg(elink_sbit_select_node, elink) # Select elink for S-bit counter
            write_backend_reg(channel_sbit_select_node, sbit_read) # Select S-bit for S-bit counter

            elink_sbit_counter_initial = read_backend_reg(elink_sbit_counter_node)
            channel_sbit_counter_initial = read_backend_reg(channel_sbit_counter_node)
            l1a_counter_initial = read_backend_reg(l1a_node)
            calpulse_counter_initial = read_backend_reg(calpulse_node)

            # Configure TTC generator
            write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.ENABLE"), 1)
            write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_CALPULSE_TO_L1A_GAP"), 50) # 50 BX between Calpulse and L1A
            write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_GAP"), l1a_bxgap)
            write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_COUNT"), nl1a)

            # Start the cyclic generator
            print ("ELINK# %02d, Channel %02d: Start L1A and Calpulsing cycle"%(elink, channel))
            file_out.write("ELINK# %02d, Channel %02d: Start L1A and Calpulsing cycle\n"%(elink, channel))
            write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_START"), 1)

            cyclic_running = read_backend_reg(cyclic_running_node)
            t0 = time()
            time_prev = t0
            if nl1a != 0:
                while cyclic_running:
                    cyclic_running = read_backend_reg(cyclic_running_node)
                    time_passed = (time()-time_prev)/60.0
                    if time_passed >= 1:
                        elink_sbit_counter = read_backend_reg(elink_sbit_counter_node) - elink_sbit_counter_initial
                        channel_sbit_counter = read_backend_reg(channel_sbit_counter_node) - channel_sbit_counter_initial
                        l1a_counter = read_backend_reg(l1a_node) - l1a_counter_initial
                        calpulse_counter = read_backend_reg(calpulse_node) - calpulse_counter_initial
                        expected_l1a = int(l1a_rate * (time()-t0) * efficiency)
                        nl1a_reg_cycles = int(expected_l1a/(2**32))
                        real_l1a_counter = nl1a_reg_cycles*(2**32) + l1a_counter
                        real_calpulse_counter = nl1a_reg_cycles*(2**32) + calpulse_counter
                        print ("Time passed: %.2f minutes, L1A counter = %.2e,  Calpulse counter = %.2e,  S-bit counter for Elink %02d = %.2e,  S-bit counter for Channel %02d = %.2e" % ((time()-t0)/60.0, real_l1a_counter, real_calpulse_counter, elink, elink_sbit_counter, channel, channel_sbit_counter))
                        file_out.write("Time passed: %.2f minutes, L1A counter = %.2e,  Calpulse counter = %.2e,  S-bit counter for Elink %02d = %.2e,  S-bit counter for Channel %02d = %.2e" % ((time()-t0)/60.0, real_l1a_counter, real_calpulse_counter, elink, elink_sbit_counter, channel, channel_sbit_counter))
                        time_prev = time()
            else:
                while ((time()-t0)/60.0) < runtime:
                    time_passed = (time()-time_prev)/60.0
                    if time_passed >= 1:
                        elink_sbit_counter = read_backend_reg(elink_sbit_counter_node) - elink_sbit_counter_initial
                        channel_sbit_counter = read_backend_reg(channel_sbit_counter_node) - channel_sbit_counter_initial
                        l1a_counter = read_backend_reg(l1a_node) - l1a_counter_initial
                        calpulse_counter = read_backend_reg(calpulse_node) - calpulse_counter_initial
                        expected_l1a = int(l1a_rate * (time()-t0) * efficiency)
                        nl1a_reg_cycles = int(expected_l1a/(2**32))
                        real_l1a_counter = nl1a_reg_cycles*(2**32) + l1a_counter
                        real_calpulse_counter = nl1a_reg_cycles*(2**32) + calpulse_counter
                        print ("Time passed: %.2f minutes, L1A counter = %.2e,  Calpulse counter = %.2e,  S-bit counter for Elink %02d = %.2e,  S-bit counter for Channel %02d = %.2e" % ((time()-t0)/60.0, real_l1a_counter, real_calpulse_counter, elink, elink_sbit_counter, channel, channel_sbit_counter))
                        file_out.write("Time passed: %.2f minutes, L1A counter = %.2e,  Calpulse counter = %.2e,  S-bit counter for Elink %02d = %.2e,  S-bit counter for Channel %02d = %.2e\n" % ((time()-t0)/60.0, real_l1a_counter, real_calpulse_counter, elink, elink_sbit_counter, channel, channel_sbit_counter))
                        time_prev = time()

            # Stop the cyclic generator
            write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)
            total_time = time() - t0
            print ("ELINK# %02d, Channel %02d, S-bit %02d: L1A and Calpulsing cycle completed in %.2f seconds (%.2f minutes)"%(elink, channel, sbit_read, total_time, total_time/60.0))
            file_out.write("ELINK# %02d, Channel %02d, S-bit %02d: L1A and Calpulsing cycle completed in %.2f seconds (%.2f minutes)\n"%(elink, channel, sbit_read, total_time, total_time/60.0))

            # Disabling the pulsing channels
            print("Disabling pulsing on channel %02d in ELINK# %02d:\n" % (channel, elink))
            file_out.write("Disabling pulsing on channel %02d in ELINK# %02d:\n\n" % (channel, elink))
            enableVfatchannel(vfat, oh_select, channel, 1, 0) # mask this channel and disable calpulsing

            elink_sbit_counter = read_backend_reg(elink_sbit_counter_node) - elink_sbit_counter_initial
            channel_sbit_counter = read_backend_reg(channel_sbit_counter_node) - channel_sbit_counter_initial
            l1a_counter = read_backend_reg(l1a_node) - l1a_counter_initial
            calpulse_counter = read_backend_reg(calpulse_node) - calpulse_counter_initial
            elink_sbit_counter_list[elink][channel] = elink_sbit_counter
            channel_sbit_counter_list[elink][channel] = channel_sbit_counter
            l1a_counter_list[elink][channel] = l1a_counter
            calpulse_counter_list[elink][channel] = calpulse_counter

        print ("")
        file_out.write("\n")

    # Unconfigure the pulsing VFAT
    print("Unconfiguring VFAT %02d" % (vfat))
    file_out.write("Unconfiguring VFAT %02d\n" % (vfat))
    configureVfat(0, vfat, oh_select, 0)

    write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.VFAT3.SC_ONLY_MODE"), 0)

    print ("\nS-Bit Error Test Results for VFAT %02d: \n"%(vfat))
    file_out.write("\nS-Bit Error Test Results for VFAT %02d: \n\n"%(vfat))

    expected_l1a = 0
    if nl1a != 0:
        expected_l1a = nl1a
    else:
        expected_l1a = int(l1a_rate * runtime * 60 * efficiency)
    real_l1a_counter = 0
    real_calpulse_counter = 0

    for elink in elink_list:
        for channel, sbit_read in zip(channel_list[elink], sbit_list[elink]):
            s_bit_expected = 0
            if system != "dryrun":
                nl1a_reg_cycles = int(expected_l1a/(2**32))
                real_l1a_counter = nl1a_reg_cycles*(2**32) + l1a_counter_list[elink][channel]
                real_calpulse_counter = nl1a_reg_cycles*(2**32) + calpulse_counter_list[elink][channel]
                s_bit_expected = real_calpulse_counter*2 # S-bit double counting
                print ("ELINK# %02d Channel %02d S-Bit %02d, Time: %.2f seconds (%.2f minutes), L1A rate: %.2f kHz, Nr. of L1A's  (effi=%.3f): %.2e, Nr. of Calpulses: %.2e \nS-bits expected for both Elink and Channel: %.2e, S-bit counter for Elink: %.2e, S-bit counter for Channel: %.2e" %(elink, channel, sbit_read, total_time, total_time/60.0, l1a_rate/1000.0, efficiency, real_l1a_counter, real_calpulse_counter, s_bit_expected, elink_sbit_counter_list[elink][channel], channel_sbit_counter_list[elink][channel]))
                file_out.write("ELINK# %02d Channel %02d S-Bit %02d, Time: %.2f seconds (%.2f minutes), L1A rate: %.2f kHz, Nr. of L1A's (effi=%.3f): %.2e, Nr. of Calpulses: %.2e, \nS-bits expected for both Elink and Channel: %.2e, S-bit counter for Elink: %.2e, S-bit counter for Channel: %.2e\n" %(elink, channel, sbit_read, total_time, total_time/60.0, l1a_rate/1000.0, efficiency, real_l1a_counter, real_calpulse_counter, s_bit_expected, elink_sbit_counter_list[elink][channel], channel_sbit_counter_list[elink][channel]))
            else:
                if nl1a != 0:
                    s_bit_expected = expected_l1a*2 # S-bit double counting
                    print ("ELINK# %02d Channel %02d S-Bit %02d, Number of L1A cycles: %.2e, \nS-bits expected for both Elink and Channel: %.2e, S-bit counter for Elink: %.2e, S-bit counter for Channel: %.2e" %(elink, channel, sbit_read, nl1a, s_bit_expected, elink_sbit_counter_list[elink][channel], channel_sbit_counter_list[elink][channel]))
                    file_out.write("ELINK# %02d Channel %02d S-Bit %02d, Number of L1A cycles: %.2e, \nS-bits expected for both Elink and Channel: %.2e, S-bit counter for Elink: %.2e, S-bit counter for Channel: %.2e\n" %(elink, channel, sbit_read, nl1a, s_bit_expected, elink_sbit_counter_list[elink][channel], channel_sbit_counter_list[elink][channel]))
                else:
                    s_bit_expected = expected_l1a*2 # S-bit double counting
                    print ("ELINK# %02d Channel %02d S-Bit %02d, Time: %.2f minutes, L1A rate: %.2f kHz, Nr. of L1A's (effi=%.3f): %.2e, \nS-bits expected for both Elink and Channel: %.2e, S-bit counter for Elink: %.2e, S-bit counter for Channel: %.2e" %(elink, channel, sbit_read, runtime, l1a_rate/1000.0, efficiency, expected_l1a, s_bit_expected, elink_sbit_counter_list[elink][channel], channel_sbit_counter_list[elink][channel]))
                    file_out.write("ELINK# %02d Channel %02d S-Bit %02d, Time: %.2f minutes, L1A rate: %.2f kHz, Nr. of L1A's (effi=%.3f): %.2e, \nS-bits expected for both Elink and Channel: %.2e, S-bit counter for Elink: %.2e, S-bit counter for Channel: %.2e\n" %(elink, channel, sbit_read, runtime, l1a_rate/1000.0, efficiency, expected_l1a, s_bit_expected, elink_sbit_counter_list[elink][channel], channel_sbit_counter_list[elink][channel]))

            # BER for Channel S-bit
            channel_n_err = s_bit_expected - channel_sbit_counter_list[elink][channel]
            if s_bit_expected == 0:
                ber = 0
                ber_ul = 0
            else:
                channel_ber = float(channel_n_err)/s_bit_expected
                channel_ber_ul = 1.0/s_bit_expected
            if channel_ber==0:
                print (Colors.GREEN + "ELINK# %02d Channel %02d S-Bit %02d: Errors = %.2e,  Bit Error Ratio (BER) < "%(elink, channel, sbit_read, channel_n_err) + "{:.2e}".format(channel_ber_ul) + Colors.ENDC)
                file_out.write("ELINK# %02d Channel %02d S-Bit %02d: Errors = %.2e,  Bit Error Ratio (BER) < "%(elink, channel, sbit_read, channel_n_err) + "{:.2e}\n".format(channel_ber_ul))
            else:
                print (Colors.YELLOW + "ELINK# %02d Channel %02d S-Bit %02d: Errors = %.2e,  Bit Error Ratio (BER) = "%(elink, channel, sbit_read, channel_n_err) + "{:.2e}".format(channel_ber) + Colors.ENDC)
                file_out.write("ELINK# %02d Channel %02d S-Bit %02d: Errors = %.2e,  Bit Error Ratio (BER) = "%(elink, channel, sbit_read, channel_n_err) + "{:.2e}\n".format(channel_ber))
            print ("")
            file_out.write("\n")

    print ("\nS-bit testing done\n")
    file_out.write("\nS-bit testing done\n\n")
    file_out.close()

if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='LpGBT VFAT S-Bit Test')
    parser.add_argument("-s", "--system", action="store", dest="system", help="system = backend or dryrun")
    #parser.add_argument("-l", "--lpgbt", action="store", dest="lpgbt", help="lpgbt = boss or sub")
    parser.add_argument("-o", "--ohid", action="store", dest="ohid", help="ohid = 0-1")
    #parser.add_argument("-g", "--gbtid", action="store", dest="gbtid", help="gbtid = 0-7 (only needed for backend)")
    parser.add_argument("-v", "--vfat", action="store", dest="vfat", help="vfat = VFAT number (0-23)")
    parser.add_argument("-e", "--elink", action="store", dest="elink", nargs='+', help="elink = list of ELINKs (0-7) for S-bits")
    parser.add_argument("-c", "--channels", action="store", dest="channels", nargs='+', help="channels = list of channels for chosen VFAT and ELINK (list allowed only for 1 elink, by default all channels used for the elinks)")
    parser.add_argument("-x", "--sbits", action="store", dest="sbits", nargs='+', help="sbit = list of sbits to read for chosen VFAT and ELINK (list allowed only for 1 elink, by default all s-bits used for the elinks)")
    parser.add_argument("-n", "--nl1a", action="store", dest="nl1a", help="nl1a = fixed number of L1A cycles")
    parser.add_argument("-t", "--time", action="store", dest="time", help="time = time for which to run the S-bit testing (in minutes)")
    parser.add_argument("-b", "--bxgap", action="store", dest="bxgap", default="500", help="bxgap = Nr. of BX between two L1A's (default = 500 i.e. 12.5 us)")
    parser.add_argument("-a", "--addr", action="store", nargs='+', dest="addr", help="addr = list of VFATs to enable HDLC addressing")
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

    if args.ohid is None:
        print(Colors.YELLOW + "Need OHID" + Colors.ENDC)
        sys.exit()
    if int(args.ohid) > 1:
        print(Colors.YELLOW + "Only OHID 0-1 allowed" + Colors.ENDC)
        sys.exit()

    if args.vfat is None:
        print (Colors.YELLOW + "Enter VFAT number" + Colors.ENDC)
        sys.exit()
    vfat = int(args.vfat)
    if vfat not in range(0,24):
        print (Colors.YELLOW + "Invalid VFAT number, only allowed 0-23" + Colors.ENDC)
        sys.exit()

    if args.elink is None:
        args.elink = ["0","1","2","3","4","5","6","7"]
        sys.exit()
    if len(args.elink)>1 and args.channels is not None:
        print (Colors.YELLOW + "Channel list allowed only for 1 elink, by default all channels used for multiple elinks" + Colors.ENDC)
        sys.exit()
    if len(args.elink)>1 and args.sbits is not None:
        print (Colors.YELLOW + "Sbit list allowed only for 1 elink, by default all sbits used for multiple elinks" + Colors.ENDC)
        sys.exit()
    if args.channels is None and args.sbits is not None:
        print (Colors.YELLOW + "Cannot be bit list if Channel list not given" + Colors.ENDC)
        sys.exit()
    if args.channels is not None and args.sbits is not None:
        if len(args.channels) != len(args.sbits):
            print (Colors.YELLOW + "Nr. of Sbits and Channels need to be the same" + Colors.ENDC)
            sys.exit()

    elink_list = []
    channel_list ={}
    sbit_list = {}
    s_bit_channel_mapping = {}

    if args.sbits is None:
        print ("")
        if not os.path.isdir("sbit_mapping_results"):
            print (Colors.YELLOW + "Run the S-bit mapping first" + Colors.ENDC)
            sys.exit()
        list_of_files = glob.glob("sbit_mapping_results/*.py")
        if len(list_of_files)>1:
            print ("Mutliple S-bit mapping results found, using latest file")
        latest_file = max(list_of_files, key=os.path.getctime)
        print ("Using S-bit mapping file: %s\n"%(latest_file.split("sbit_mapping_results/")[1]))
        with open(latest_file) as input_file:
            s_bit_channel_mapping = json.load(input_file)

    for e in args.elink:
        elink = int(e)
        if elink not in range(0,8):
            print (Colors.YELLOW + "Invalid ELINK number, only allowed 0-7" + Colors.ENDC)
            sys.exit()
        elink_list.append(elink)
        channel_list[elink] = []
        sbit_list[elink] = []

        if args.channels is None:
            for c in range(0,16):
                sbit_input_file = s_bit_channel_mapping[str(vfat)][str(elink)][str(elink*16 + c)]
                if sbit_input_file == -9999:
                    print (Colors.YELLOW + "Channel %02d is bad, skipping"%(elink*16 + c) + Colors.ENDC)
                    continue
                channel_list[elink].append(elink*16 + c)
                #sbit_list[elink].append(elink*8 + int(c/2))
                sbit_list[elink].append(sbit_input_file)
        else:
            for c in args.channels:
                c_int = int(c)
                if c_int not in range(elink*16, elink*16+16):
                    print (Colors.YELLOW + "Invalid Channel number for selected ELINK" + Colors.ENDC)
                    sys.exit()
                channel_list[elink].append(c_int)
                if args.sbits is None:
                    #sbit_list[elink].append(int(c_int/2))
                    sbit_input_file = s_bit_channel_mapping[str(vfat)][str(elink)][str(c_int)]
                    if sbit_input_file == -9999:
                        print (Colors.YELLOW + "Channel %02d is bad (from S-bit phase scan)"%(c_int) + Colors.ENDC)
                        sys.exit()
                    sbit_list[elink].append(sbit_input_file)
            if args.sbits is not None:
                for sbit in args.sbits:
                    sbit_int = int(sbit)
                    sbit_list[elink].append(sbit_int)

    nl1a = 0
    if args.nl1a is not None:
        nl1a = int(args.nl1a)
        if args.time is not None:
            print (Colors.YELLOW + "Cannot give both time and number of L1A cycles" + Colors.ENDC)
            sys.exit()
        if nl1a > (2**32 - 1):
            print (Colors.YELLOW + "Number of L1A cycles can be maximum 4.29e9. Using time option for longer tests" + Colors.ENDC)
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

    if args.addr is not None:
        print ("Enabling VFAT addressing for plugin cards on slots: ")
        print (args.addr)
        addr_list = []
        for a in args.addr:
            a_int = int(a)
            if a_int not in range(0,24):
                print (Colors.YELLOW + "Invalid VFAT number for HDLC addressing, only allowed 0-23" + Colors.ENDC)
                sys.exit()
            addr_list.append(a_int)
        enable_hdlc_addressing(addr_list)

    # Parsing Registers XML File
    print("Parsing xml file...")
    parseXML()
    print("Parsing complete...")

    # Initialization (for CHeeseCake: reset and config_select)
    rw_initialize(args.system)
    print("Initialization Done\n")
    
    # Running Phase Scan
    try:
        lpgbt_vfat_sbit(args.system, int(args.ohid), vfat, elink_list, channel_list, sbit_list, nl1a, runtime, l1a_bxgap)
    except KeyboardInterrupt:
        print (Colors.RED + "Keyboard Interrupt encountered" + Colors.ENDC)
        rw_terminate()
    except EOFError:
        print (Colors.RED + "\nEOF Error" + Colors.ENDC)
        rw_terminate()

    # Termination
    rw_terminate()




