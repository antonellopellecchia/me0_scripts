from rw_reg_lpgbt import *
from time import sleep, time
import datetime
import sys
import argparse
import random
import glob
import json
from lpgbt_vfat_config import configureVfat, enableVfatchannel

s_bit_channel_mapping = {}
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


def lpgbt_vfat_sbit(system, oh_select, vfat_list, elink_list, step, runtime):
    if not os.path.exists("sbit_noise_results"):
        os.makedirs("sbit_noise_results")
    now = str(datetime.datetime.now())[:16]
    now = now.replace(":", "_")
    now = now.replace(" ", "_")
    foldername = "sbit_noise_results/"
    filename = foldername + "vfat_sbit_noise_" + now + ".txt"
    file_out = open(filename,"w+")
    file_out.write("vfat    elink    threshold    fired    time\n")

    vfat_oh_link_reset()
    global_reset()
    sleep(0.1)
    write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.VFAT3.SC_ONLY_MODE"), 1)

    sbit_data = {}
    # Check ready and get nodes
    for vfat in vfat_list:
        lpgbt, gbt_select, elink, gpio = vfat_to_gbt_elink_gpio(vfat)
        check_lpgbt_link_ready(oh_select, gbt_select)

        print("Configuring VFAT %d" % (vfat))
        configureVfat(1, vfat, oh_select, 0)
        for channel in range(0,128):
            enableVfatchannel(vfat, oh_select, channel, 0, 0) # unmask all channels and disable calpulsing

        link_good_node = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.LINK_GOOD" % (oh_select, vfat))
        sync_error_node = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.SYNC_ERR_CNT" % (oh_select, vfat))
        link_good = read_backend_reg(link_good_node)
        sync_err = read_backend_reg(sync_error_node)
        if system!="dryrun" and (link_good == 0 or sync_err > 0):
            print (Colors.RED + "Link is bad for VFAT# %02d"%(vfat) + Colors.ENDC)
            rw_terminate()

        sbit_data[vfat] = {}
        for elink in elink_list:
            sbit_data[vfat][elink] = {}
            for thr in range(0,256,step):
                sbit_data[vfat][elink][thr] = {}
                sbit_data[vfat][elink][thr]["time"] = -9999
                sbit_data[vfat][elink][thr]["fired"] = -9999

    # Nodes for Sbit counters
    vfat_sbit_select_node = get_rwreg_node("GEM_AMC.TRIGGER.TEST_SEL_VFAT_SBIT_ME0") # VFAT for reading S-bits
    elink_sbit_select_node = get_rwreg_node("GEM_AMC.TRIGGER.TEST_SEL_ELINK_SBIT_ME0") # Node for selecting Elink to count
    channel_sbit_select_node = get_rwreg_node("GEM_AMC.TRIGGER.TEST_SEL_SBIT_ME0") # Node for selecting S-bit to count
    elink_sbit_counter_node = get_rwreg_node("GEM_AMC.TRIGGER.TEST_SBIT0XE_COUNT_ME0") # S-bit counter for elink
    channel_sbit_counter_node = get_rwreg_node("GEM_AMC.TRIGGER.TEST_SBIT0XS_COUNT_ME0") # S-bit counter for specific channel
    reset_sbit_counter_node = get_rwreg_node("GEM_AMC.TRIGGER.CTRL.SBIT_TEST_RESET")  # To reset all S-bit counters

    dac_node = {}
    dac = "CFG_THR_ARM_DAC"
    for vfat in vfat_list:
        dac_node[vfat] = get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%d.%s"%(oh_select, vfat, dac))

    print ("\nRunning Sbit Noise Scans for VFATs:")
    print (vfat_list)
    print ("")

    # Looping over elinks
    for elink in elink_list:
        print ("Elink: %d"%elink)
        write_backend_reg(elink_sbit_select_node, elink)
        for vfat in vfat_list:
            write_backend_reg(vfat_sbit_select_node, vfat)

            # Looping over threshold
            for thr in range(0,256,step):
                #print ("    Threshold: %d"%thr)
                write_backend_reg(dac_node[vfat], thr)
                sleep(1e-3)

                # Count hits in elink in given time
                write_backend_reg(reset_sbit_counter_node, 1)
                sleep(runtime)
                sbit_data[vfat][elink][thr]["fired"] = read_backend_reg(elink_sbit_counter_node)
                sbit_data[vfat][elink][thr]["time"] = runtime 
            # End of charge loop
        # End of VFAT loop
    # End of channel loop
    print ("")

    # Disable channels on VFATs
    for vfat in vfat_list:
        print("Unconfiguring VFAT %d" % (vfat))
        configureVfat(0, vfat, oh_select, 0)
    write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.VFAT3.SC_ONLY_MODE"), 0)

    # Writing Results
    for vfat in vfat_list:
        for elink in elink_list:
            for thr in range(0,256,1):
                if thr not in sbit_data[vfat][elink]:
                    continue
                file_out.write("%d    %d    %d    %d    %f\n"%(vfat, elink, thr, sbit_data[vfat][elink][thr]["fired"], sbit_data[vfat][elink][thr]["time"]))

    print ("")
    file_out.close()


if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='LpGBT VFAT S-Bit Noise Rate')
    parser.add_argument("-s", "--system", action="store", dest="system", help="system = backend or dryrun")
    #parser.add_argument("-l", "--lpgbt", action="store", dest="lpgbt", help="lpgbt = boss or sub")
    parser.add_argument("-o", "--ohid", action="store", dest="ohid", help="ohid = 0-1")
    #parser.add_argument("-g", "--gbtid", action="store", dest="gbtid", help="gbtid = 0-7 (only needed for backend)")
    parser.add_argument("-v", "--vfats", action="store", dest="vfats", nargs='+', help="vfats = VFAT number (0-23)")
    parser.add_argument("-e", "--elinks", action="store", nargs='+', dest="elinks", help="elinks = list of elinks (default: 0-7)")
    parser.add_argument("-t", "--step", action="store", dest="step", default="1", help="step = Step size for SCurve scan (default=1)")
    parser.add_argument("-m", "--time", action="store", dest="time", default="0.001", help="time = time for each elink (default= 1 ms)")
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

    step = int(args.step)
    if step not in range(1,257):
        print (Colors.YELLOW + "Step size can only be between 1 and 256" + Colors.ENDC)
        sys.exit()

    elink_list = []
    if args.elinks is None:
        elink_list = range(0,8)
    else:
        for e in args.elinks:
            e_int = int(e)
            if e_int not in range(0,8):
                print (Colors.YELLOW + "Invalid elink, only allowed 0-7" + Colors.ENDC)
                sys.exit()
            elink_list.append(e_int)

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
    
    # Running Sbit SCurve
    try:
        lpgbt_vfat_sbit(args.system, int(args.ohid), vfat_list, elink_list, step, float(args.time))
    except KeyboardInterrupt:
        print (Colors.RED + "Keyboard Interrupt encountered" + Colors.ENDC)
        rw_terminate()
    except EOFError:
        print (Colors.RED + "\nEOF Error" + Colors.ENDC)
        rw_terminate()

    # Termination
    rw_terminate()




