from rw_reg_lpgbt import *
from time import sleep, time
import datetime
import sys
import argparse
import random
import json
from lpgbt_vfat_config import configureVfat, enableVfatchannel

config_boss_filename = "config_boss.txt"
config_sub_filename = "config_sub.txt"
config_boss = {}
config_sub = {}

def getConfig (filename):
    f = open(filename, 'r')
    reg_map = {}
    for line in f.readlines():
        reg = int(line.split()[0], 16)
        data = int(line.split()[1], 16)
        reg_map[reg] = data
    f.close()
    return reg_map


def lpgbt_vfat_sbit(system, oh_select, vfat_list, nl1a, l1a_bxgap, best_phase):
    print ("LPGBT VFAT S-Bit Phase Scan\n")

    errs = [[[0 for phase in range(16)] for elink in range(0,8)] for vfat in range(24)]

    global_reset()
    sleep(0.1)
    write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.VFAT3.SC_ONLY_MODE"), 1)

    # Reading S-bit counters
    cyclic_running_node = get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_RUNNING")
    l1a_node = get_rwreg_node("GEM_AMC.TTC.CMD_COUNTERS.L1A")
    calpulse_node = get_rwreg_node("GEM_AMC.TTC.CMD_COUNTERS.CALPULSE")

    elink_sbit_select_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SEL_ELINK_SBIT_ME0") # Node for selecting Elink to count
    channel_sbit_select_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SEL_SBIT_ME0") # Node for selecting S-bit to count
    elink_sbit_counter_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SBIT0XE_COUNT_ME0") # S-bit counter for elink
    channel_sbit_counter_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SBIT0XS_COUNT_ME0") # S-bit counter for specific channel
    reset_sbit_counter_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.CTRL.SBIT_TEST_RESET")  # To reset all S-bit counters

    for vfat in vfat_list:
        lpgbt, gbt_select, elink_daq, gpio = vfat_to_gbt_elink_gpio(vfat)
        check_lpgbt_link_ready(oh_select, gbt_select)

        link_good = read_backend_reg(get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.LINK_GOOD" % (oh_select, vfat)))
        sync_err = read_backend_reg(get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.SYNC_ERR_CNT" % (oh_select, vfat)))
        if system!="dryrun" and (link_good == 0 or sync_err > 0):
            print (Colors.RED + "Link is bad for VFAT# %02d"%(vfat) + Colors.ENDC)
            rw_terminate()

        # Configure the pulsing VFAT
        print("Configuring VFAT %02d" % (vfat))
        configureVfat(1, vfat, oh_select, 0)
        for i in range(128):
            enableVfatchannel(vfat, oh_select, i, 1, 0) # mask all channels and disable calpulsing
        print ("")

    for phase in range(0, 16):
        print('Scanning phase %d' % phase)

        # set phases for all vfats under test
        for vfat in vfat_list:
            sbit_elinks = vfat_to_sbit_elink(vfat)
            for elink in range(0,8):
                setVfatSbitPhase(system, oh_select, vfat, sbit_elinks[elink], phase)

        # Reset TTC generator
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.ENABLE"), 1)
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_CALPULSE_TO_L1A_GAP"), 50)
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_GAP"), l1a_bxgap)
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_COUNT"), nl1a)

        s_bit_channel_mapping = {}
        print ("Checking errors: ")
        for vfat in vfat_list:
            lpgbt, gbt_select, elink_daq, gpio = vfat_to_gbt_elink_gpio(vfat)
            # Reset the link, give some time to accumulate any sync errors and then check VFAT comms
            sleep(0.1)
            vfat_oh_link_reset()
            sleep(0.1)

            write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SEL_VFAT_SBIT_ME0"), vfat) # Select VFAT for reading S-bits

            s_bit_channel_mapping[vfat] = {}
            # Looping over all 8 elinks
            for elink in range(0,8):
                write_backend_reg(elink_sbit_select_node, elink) # Select elink for S-bit counter
                s_bit_channel_mapping[vfat][elink] = {}
                s_bit_matches = {}

                # Looping over all channels in that elink
                for channel in range(elink*16,elink*16+16):
                    # Enabling the pulsing channel
                    enableVfatchannel(vfat, oh_select, channel, 0, 1) # unmask this channel and enable calpulsing

                    channel_sbit_counter_initial = {}
                    channel_sbit_counter_final = {}
                    sbit_channel_match = 0
                    s_bit_channel_mapping[vfat][elink][channel] = -9999

                    # Looping over all s-bits in that elink
                    for sbit in range(elink*8,elink*8+8):
                        # Reset L1A, CalPulse and S-bit counters
                        global_reset()
                        write_backend_reg(reset_sbit_counter_node, 1)

                        write_backend_reg(channel_sbit_select_node, sbit) # Select S-bit for S-bit counter
                        channel_sbit_counter_initial[sbit] = read_backend_reg(channel_sbit_counter_node)
                        s_bit_matches[sbit] = 0

                        elink_sbit_counter_initial = read_backend_reg(elink_sbit_counter_node)
                        l1a_counter_initial = read_backend_reg(l1a_node)
                        calpulse_counter_initial = read_backend_reg(calpulse_node)

                        # Start the cyclic generator
                        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_START"), 1)
                        cyclic_running = read_backend_reg(cyclic_running_node)
                        while cyclic_running:
                            cyclic_running = read_backend_reg(cyclic_running_node)

                        # Stop the cyclic generator
                        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)

                        elink_sbit_counter_final = read_backend_reg(elink_sbit_counter_node)
                        l1a_counter = read_backend_reg(l1a_node) - l1a_counter_initial
                        calpulse_counter = read_backend_reg(calpulse_node) - calpulse_counter_initial

                        if (elink_sbit_counter_final - elink_sbit_counter_initial) == 0:
                            # Elink did not register a hit
                            s_bit_channel_mapping[vfat][elink][channel] = -9999
                            break
                        channel_sbit_counter_final[sbit] = read_backend_reg(channel_sbit_counter_node)

                        if (channel_sbit_counter_final[sbit] - channel_sbit_counter_initial[sbit]) > 0:
                            if sbit_channel_match == 1:
                                # Multiple S-bits registered hits for calpulse on this channel
                                s_bit_channel_mapping[vfat][elink][channel] = -9999
                                break
                            if s_bit_matches[sbit] >= 2:
                                # S-bit already matched to 2 channels
                                s_bit_channel_mapping[vfat][elink][channel] = -9999
                                break
                            if s_bit_matches[sbit] == 1:
                                if s_bit_channel_mapping[vfat][elink][channel-1] != sbit:
                                    # S-bit matched to a different channel than the previous one
                                    s_bit_channel_mapping[vfat][elink][channel] = -9999
                                    break
                                if channel%2==0:
                                    # S-bit already matched to an earlier odd numbered channel"
                                    s_bit_channel_mapping[vfat][elink][channel] = -9999
                                    break
                            s_bit_channel_mapping[vfat][elink][channel] = sbit
                            sbit_channel_match = 1
                            s_bit_matches[sbit] += 1
                    # End of S-bit loop for this channel

                    if s_bit_channel_mapping[vfat][elink][channel] == -9999:
                        errs[vfat][elink][phase] += 1

                    # Disabling the pulsing channels
                    enableVfatchannel(vfat, oh_select, channel, 1, 0) # mask this channel and disable calpulsing
                # End of Channel loop

                if errs[vfat][elink][phase] == 0:
                    print (Colors.GREEN + "Results of VFAT %02d SBit ELINK %02d: nr. of channel errors=%d"%(vfat, elink, errs[vfat][elink][phase]) + Colors.ENDC)
                elif errs[vfat][elink][phase] < 16:
                    print (Colors.YELLOW + "Results of VFAT %02d SBit ELINK %02d: nr. of channel errors=%d"%(vfat, elink, errs[vfat][elink][phase]) + Colors.ENDC)
                else:
                    print (Colors.RED + "Results of VFAT %02d SBit ELINK %02d: nr. of channel errors=%d"%(vfat, elink, errs[vfat][elink][phase]) + Colors.ENDC)

            # End of Elink loop
            print ("")
        # End of VFAT loop
    # End of Phase loop

    for vfat in vfat_list:
        # Unconfigure the pulsing VFAT
        print("Unconfiguring VFAT %02d" % (vfat))
        configureVfat(0, vfat, oh_select, 0)
        print ("")

    for vfat in vfat_list:
        centers = 8*[0]
        widths  = 8*[0]
        for elink in range(0,8):
            centers[elink], widths[elink] = find_phase_center(errs[vfat][elink])

        print ("\nVFAT %02d :" %(vfat))
        bestphase_elink = 8*[0]
        for elink in range(0,8):
            sys.stdout.write("  ELINK %02d: " % (elink))
            for phase in range(0, 16):
                if (widths[elink]>0 and phase==centers[elink]):
                    char=Colors.GREEN + "+" + Colors.ENDC
                    bestphase_elink[elink] = phase
                elif (errs[vfat][elink][phase]):
                    char=Colors.RED + "-" + Colors.ENDC
                else:
                    char = Colors.YELLOW + "x" + Colors.ENDC

                sys.stdout.write("%s" % char)
                sys.stdout.flush()
            if widths[elink]<3:
                sys.stdout.write(Colors.RED + " (center=%d, width=%d) BAD\n" % (centers[elink], widths[elink]) + Colors.ENDC)
            elif widths[elink]<5:
                sys.stdout.write(Colors.YELLOW + " (center=%d, width=%d) WARNING\n" % (centers[elink], widths[elink]) + Colors.ENDC)
            else:
                sys.stdout.write(Colors.GREEN + " (center=%d, width=%d) GOOD\n" % (centers[elink], widths[elink]) + Colors.ENDC)
            sys.stdout.flush()

        # set phases for all elinks for this vfat
        print ("\nVFAT %02d: Setting all ELINK phases to best phases: "%(vfat))
        sbit_elinks = vfat_to_sbit_elink(vfat)
        for elink in range(0,8):
            set_bestphase = 0
            if best_phase is None:
                set_bestphase = bestphase_elink[elink]
            else:
                set_bestphase = int(best_phase,16)
            setVfatSbitPhase(system, oh_select, vfat, sbit_elinks[elink], set_bestphase)
            print ("VFAT %02d: Phase set for ELINK %02d to: %s" % (vfat, elink, hex(set_bestphase)))

    sleep(0.1)
    vfat_oh_link_reset()
    print ("")

    write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.VFAT3.SC_ONLY_MODE"), 0)
    print ("\nS-bit phase scan done\n")


def find_phase_center(err_list):
    # find the centers
    ngood        = 0
    ngood_max    = 0
    ngood_edge   = 0
    ngood_center = 0

    # duplicate the err_list to handle the wraparound
    err_list_doubled = err_list + err_list
    phase_max = len(err_list)-1

    for phase in range(0,len(err_list_doubled)):
        if (err_list_doubled[phase] == 0):
            ngood+=1
        else: # hit an edge
            if (ngood > 0 and ngood >= ngood_max):
                ngood_max  = ngood
                ngood_edge = phase
            ngood=0

    # cover the case when there are no edges, just pick the center
    if (ngood==len(err_list_doubled)):
        ngood_max  = int(ngood/2)
        ngood_edge =len(err_list_doubled)-1

    if (ngood_max>0):
        ngood_width = ngood_max
        # even windows
        if (ngood_max % 2 == 0):
            ngood_center=ngood_edge-(ngood_max/2)-1
            print (ngood_edge, ngood_max)
            if (err_list_doubled[ngood_edge] > err_list_doubled[ngood_edge-ngood_max-1]):
                ngood_center=ngood_center
            else:
                ngood_center=ngood_center+1
        # oddwindows
        else:
            ngood_center=ngood_edge-(ngood_max/2)-1;

    ngood_center = ngood_center % phase_max - 1

    if (ngood_max==0):
        ngood_center=0

    return ngood_center, ngood_max


def setVfatSbitPhase(system, oh_select, vfat, sbit_elink, phase):
    lpgbt, gbt_select, rx_elink, gpio = vfat_to_gbt_elink_gpio(vfat)

    if lpgbt == "boss":
        config = config_boss
    elif lpgbt == "sub":
        config = config_sub

    # set phase
    GBT_ELINK_SAMPLE_PHASE_BASE_REG = 0x0CC
    addr = GBT_ELINK_SAMPLE_PHASE_BASE_REG + sbit_elink
    value = (config[addr] & 0x0f) | (phase << 4)

    check_lpgbt_link_ready(oh_select, gbt_select)
    select_ic_link(oh_select, gbt_select)
    if system!= "dryrun" and system!= "backend":
        check_rom_readback()
    mpoke(addr, value)
    sleep(0.000001) # writing too fast for CVP13

if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='LpGBT VFAT S-Bit Phase Scan')
    parser.add_argument("-s", "--system", action="store", dest="system", help="system = backend or dryrun")
    #parser.add_argument("-l", "--lpgbt", action="store", dest="lpgbt", help="lpgbt = boss or sub")
    parser.add_argument("-o", "--ohid", action="store", dest="ohid", help="ohid = 0-1")
    #parser.add_argument("-g", "--gbtid", action="store", dest="gbtid", help="gbtid = 0-7 (only needed for backend)")
    parser.add_argument("-v", "--vfats", action="store", nargs='+', dest="vfats", help="vfats = list of VFAT numbers (0-23)")
    parser.add_argument("-b", "--bestphase", action="store", dest="bestphase", help="bestphase = Best value of the elinkRX phase (in hex), calculated from phase scan by default")
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

    if args.vfats is None:
        print (Colors.YELLOW + "Enter VFAT numbers" + Colors.ENDC)
        sys.exit()
    vfat_list = []
    for v in args.vfats:
        v_int = int(v)
        if v_int not in range(0,24):
            print (Colors.YELLOW + "Invalid VFAT number, only allowed 0-23" + Colors.ENDC)
            sys.exit()
        vfat_list.append(v_int)

    nl1a = 100 # Nr. of L1A's
    l1a_bxgap = 500 # Gap between 2 L1A's in nr. of BX's

    if args.bestphase is not None:
        if "0x" not in args.bestphase:
            print (Colors.YELLOW + "Enter best phase in hex format" + Colors.ENDC)
            sys.exit()
        if int(args.bestphase, 16)>16:
            print (Colors.YELLOW + "Phase can only be 4 bits" + Colors.ENDC)
            sys.exit()
        
    # Parsing Registers XML File
    print("Parsing xml file...")
    parseXML()
    print("Parsing complete...")

    # Initialization (for CHeeseCake: reset and config_select)
    rw_initialize(args.system)
    print("Initialization Done\n")

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

    if not os.path.isfile(config_boss_filename):
        print (Colors.YELLOW + "Missing config file for boss: config_boss.txt" + Colors.ENDC)
        sys.exit()

    if not os.path.isfile(config_sub_filename):
        print (Colors.YELLOW + "Missing config file for sub: sub_boss.txt" + Colors.ENDC)
        sys.exit()

    config_boss = getConfig(config_boss_filename)
    config_sub  = getConfig(config_sub_filename)

    # Running Phase Scan
    try:
        lpgbt_vfat_sbit(args.system, int(args.ohid), vfat_list, nl1a, l1a_bxgap, args.bestphase)
    except KeyboardInterrupt:
        print (Colors.RED + "Keyboard Interrupt encountered" + Colors.ENDC)
        rw_terminate()
    except EOFError:
        print (Colors.RED + "\nEOF Error" + Colors.ENDC)
        rw_terminate()

    # Termination
    rw_terminate()




