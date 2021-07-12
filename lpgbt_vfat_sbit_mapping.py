from rw_reg_lpgbt import *
from time import sleep, time
import datetime
import sys
import argparse
import random
import json
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

def vfat_to_oh_gbt_elink(vfat):
    lpgbt = VFAT_TO_ELINK[vfat][0]
    ohid  = VFAT_TO_ELINK[vfat][1]
    gbtid = VFAT_TO_ELINK[vfat][2]
    elink = VFAT_TO_ELINK[vfat][3]
    return lpgbt, ohid, gbtid, elink

def lpgbt_vfat_sbit(system, vfat_list, nl1a, l1a_bxgap):
    print ("LPGBT VFAT S-Bit Mapping\n")

    vfat_oh_link_reset()
    global_reset()
    sleep(0.1)
    write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.VFAT3.SC_ONLY_MODE"), 1)

    s_bit_channel_mapping = {}

    for vfat in vfat_list:
        print ("Testing VFAT#: %02d" %(vfat))
        print ("")
        lpgbt, oh_select, gbt_select, rx_elink = vfat_to_oh_gbt_elink(vfat)
        check_lpgbt_link_ready(oh_select, gbt_select)

        link_good = read_backend_reg(get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.LINK_GOOD" % (oh_select, vfat-6*oh_select)))
        sync_err = read_backend_reg(get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.SYNC_ERR_CNT" % (oh_select, vfat-6*oh_select)))
        if system!="dryrun" and (link_good == 0 or sync_err > 0):
            print (Colors.RED + "Link is bad for VFAT# %02d"%(vfat) + Colors.ENDC)
            rw_terminate()

        # Reset TTC generator
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)

        # Reading S-bit counter
        cyclic_running_node = get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_RUNNING")
        l1a_node = get_rwreg_node("GEM_AMC.TTC.CMD_COUNTERS.L1A")
        calpulse_node = get_rwreg_node("GEM_AMC.TTC.CMD_COUNTERS.CALPULSE")

        write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SEL_VFAT_SBIT_ME0"), vfat) # Select VFAT for reading S-bits
        elink_sbit_select_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SEL_ELINK_SBIT_ME0") # Node for selecting Elink to count
        channel_sbit_select_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SEL_SBIT_ME0") # Node for selecting S-bit to count
        elink_sbit_counter_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SBIT0XE_COUNT_ME0") # S-bit counter for elink
        channel_sbit_counter_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.TEST_SBIT0XS_COUNT_ME0") # S-bit counter for specific channel
        reset_sbit_counter_node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.CTRL.SBIT_TEST_RESET")  # To reset all S-bit counters

        # Configure the pulsing VFAT
        print("Configuring VFAT %02d" % (vfat))
        configureVfat(1, vfat-6*oh_select, oh_select, 0)
        for i in range(128):
            enableVfatchannel(vfat-6*oh_select, oh_select, i, 1, 0) # mask all channels and disable calpulsing
        print ("")

        s_bit_channel_mapping[vfat] = {}
        # Looping over all 8 elinks
        for elink in range(0,8):
            print ("Phase scan for S-bits in ELINK# %02d" %(elink))
            write_backend_reg(elink_sbit_select_node, elink) # Select elink for S-bit counter

            s_bit_channel_mapping[vfat][elink] = {}
            s_bit_matches = {}
            # Looping over all channels in that elink
            for channel in range(elink*16,elink*16+16):
                # Enabling the pulsing channel
                enableVfatchannel(vfat-6*oh_select, oh_select, channel, 0, 1) # unmask this channel and enable calpulsing

                channel_sbit_counter_final = {}
                sbit_channel_match = 0
                s_bit_channel_mapping[vfat][elink][channel] = -9999

                # Looping over all s-bits in that elink
                for sbit in range(elink*8,elink*8+8):
                    # Reset L1A, CalPulse and S-bit counters
                    global_reset()
                    write_backend_reg(reset_sbit_counter_node, 1)

                    write_backend_reg(channel_sbit_select_node, sbit) # Select S-bit for S-bit counter
                    s_bit_matches[sbit] = 0

                    # Configure TTC generator
                    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.ENABLE"), 1)
                    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_CALPULSE_TO_L1A_GAP"), 50)
                    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_GAP"), l1a_bxgap)
                    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_COUNT"), nl1a)

                    # Start the cyclic generator
                    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_START"), 1)
                    cyclic_running = read_backend_reg(cyclic_running_node)
                    while cyclic_running:
                        cyclic_running = read_backend_reg(cyclic_running_node)

                    # Stop the cyclic generator
                    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)

                    elink_sbit_counter_final = read_backend_reg(elink_sbit_counter_node)
                    l1a_counter = read_backend_reg(l1a_node)
                    calpulse_counter = read_backend_reg(calpulse_node)

                    if system!="dryrun" and l1a_counter != nl1a:
                        print (Colors.RED + "ERROR: Number of L1A's incorrect" + Colors.ENDC)
                        rw_terminate()
                    if system!="dryrun" and elink_sbit_counter_final == 0:
                        print (Colors.YELLOW + "WARNING: Elink %02d did not register any S-bit for calpulse on channel %02d"%(elink, channel) + Colors.ENDC)
                        s_bit_channel_mapping[vfat][elink][channel] = -9999
                        break
                    channel_sbit_counter_final[sbit] = read_backend_reg(channel_sbit_counter_node)

                    if channel_sbit_counter_final[sbit] > 0:
                        if sbit_channel_match == 1:
                            print (Colors.YELLOW + "WARNING: Multiple S-bits registered hits for calpulse on channel %02d"%(channel) + Colors.ENDC)
                            s_bit_channel_mapping[vfat][elink][channel] = -9999
                            break
                        if s_bit_matches[sbit] > 2:
                            print (Colors.YELLOW + "WARNING: S-bit %02d already matched to 2 channels"%(sbit) + Colors.ENDC)
                            s_bit_channel_mapping[vfat][elink][channel] = -9999
                            break
                        if s_bit_matches[sbit] == 1:
                            if s_bit_channel_mapping[vfat][elink][channel-1] != sbit:
                                print (Colors.YELLOW + "WARNING: S-bit %02d matched to a different channel than the previous one"%(sbit) + Colors.ENDC)
                                s_bit_channel_mapping[vfat][elink][channel] = -9999
                                break
                            if channel%2==0:
                                print (Colors.YELLOW + "WARNING: S-bit %02d already matched to an earlier odd numbered channel"%(sbit) + Colors.ENDC)
                                s_bit_channel_mapping[vfat][elink][channel] = -9999
                                break
                        s_bit_channel_mapping[vfat][elink][channel] = sbit
                        sbit_channel_match = 1
                        s_bit_matches[sbit] += 1
                    # End of S-bit loop for this channel

                # Disabling the pulsing channels
                enableVfatchannel(vfat-6*oh_select, oh_select, channel, 1, 0) # mask this channel and disable calpulsing
                # End of Channel loop

            print ("")
            # End of Elink loop

        # Unconfigure the pulsing VFAT
        print("Unconfiguring VFAT %02d" % (vfat))
        configureVfat(0, vfat-6*oh_select, oh_select, 0)
        print ("")
        # End of VFAT loop

    if not os.path.isdir("sbit_mapping_results"):
        os.mkdir("sbit_mapping_results")
    now = str(datetime.datetime.now())[:16]
    now = now.replace(":", "_")
    now = now.replace(" ", "_")
    filename = "sbit_mapping_results/sbit_mapping_results_"+now+".py"
    with open(filename, 'w') as file:
        file.write(json.dumps(s_bit_channel_mapping))

    print ("S-bit Mapping Results: \n")
    for vfat in s_bit_channel_mapping:
        print ("VFAT %02d: "%(vfat))
        for elink in s_bit_channel_mapping[vfat]:
            print ("  ELINK %02d: "%(elink))
            for channel in s_bit_channel_mapping[vfat][elink]:
                if s_bit_channel_mapping[vfat][elink][channel] == -9999:
                    print (Colors.RED + "    Channel %02d:  S-bit %02d"%(channel, s_bit_channel_mapping[vfat][elink][channel]) + Colors.ENDC)
                else:
                    print (Colors.GREEN + "    Channel %02d:  S-bit %02d"%(channel, s_bit_channel_mapping[vfat][elink][channel]) + Colors.ENDC)
        print ("")

    write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.VFAT3.SC_ONLY_MODE"), 0)
    print ("\nS-bit mapping done\n")

if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='LpGBT VFAT S-Bit Mapping')
    parser.add_argument("-s", "--system", action="store", dest="system", help="system = backend or dryrun")
    #parser.add_argument("-l", "--lpgbt", action="store", dest="lpgbt", help="lpgbt = boss or sub")
    parser.add_argument("-v", "--vfat", action="store", dest="vfat", nargs='+', help="vfat = list of VFATs (0-11)")
    #parser.add_argument("-o", "--ohid", action="store", dest="ohid", help="ohid = 0-7 (only needed for backend)")
    #parser.add_argument("-g", "--gbtid", action="store", dest="gbtid", help="gbtid = 0, 1 (only needed for backend)")
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
        print (Colors.YELLOW + "Enter VFAT numbers" + Colors.ENDC)
        sys.exit()
    vfat_list = []
    for vfat in args.vfat:
        v = int(vfat)
        if v not in range(0,12):
            print (Colors.YELLOW + "Invalid VFAT number, only allowed 0-11" + Colors.ENDC)
            sys.exit()
        vfat_list.append(v)

    nl1a = 100 # Nr. of L1A's
    l1a_bxgap = 500 # Gap between 2 L1A's in nr. of BX's

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
        lpgbt_vfat_sbit(args.system, vfat_list, nl1a, l1a_bxgap)
    except KeyboardInterrupt:
        print (Colors.RED + "Keyboard Interrupt encountered" + Colors.ENDC)
        rw_terminate()
    except EOFError:
        print (Colors.RED + "\nEOF Error" + Colors.ENDC)
        rw_terminate()

    # Termination
    rw_terminate()




