from rw_reg_lpgbt import *
from time import sleep, time
import sys
import argparse
import random
import datetime

def lpgbt_vfat_set_dac_calibration(system, oh_select, vfat_list, irefs, vrefs):
    print ("VFATs to be configured:")
    print (vfat_list)
    print ("")

    vfat_oh_link_reset()
    sleep(0.1)

    link_good_node = {}
    sync_error_node = {}
    dac_node = {}
    vfat_cfg_run_node = {}
    vfat_cfg_calmode_node = {}
    adc_monitor_select_node = {}
    adc0_cached_node = {}
    adc0_update_node = {}
    adc1_cached_node = {}
    adc1_update_node = {}
    dac_scan_results = {}

    # Check ready and get nodes
    for vfat in vfat_list:
        print("Setting calibration parameters for vfat " + str(vfat) + "...")
        iref, vref = irefs[vfat], vrefs[vfat]

        lpgbt, gbt_select, elink, gpio = vfat_to_gbt_elink_gpio(vfat)
        check_lpgbt_link_ready(oh_select, gbt_select)

        link_good_node[vfat] = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.LINK_GOOD" % (oh_select, vfat))
        sync_error_node[vfat] = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.SYNC_ERR_CNT" % (oh_select, vfat))
        link_good = read_backend_reg(link_good_node[vfat])
        sync_err = read_backend_reg(sync_error_node[vfat])
        if system!="dryrun" and (link_good == 0 or sync_err > 0):
            print (Colors.RED + "Link is bad for VFAT# %02d"%(vfat) + Colors.ENDC)
            rw_terminate()

        write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%d.CFG_IREF" % (oh_select, vfat)) , iref)
        write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%d.CFG_VREF_ADC" % (oh_select, vfat)) , vref)

def read_txt_config(config_file_path):
    config_lines = open(config_file_path).readlines()
    config_pairs = [ l.split('\t') for l in config_lines ]
    config_pairs = [ (int(p[0]), int(p[1])) for p in config_pairs ]
    config_dict = dict(config_pairs)
    return config_dict

if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='LpGBT VFAT DAC Scan')
    parser.add_argument("-s", "--system", action="store", dest="system", help="system = backend or dryrun")
    parser.add_argument("-o", "--ohid", action="store", dest="ohid", help="ohid = 0-1")
    parser.add_argument("-v", "--vfats", action="store", nargs='+', dest="vfats", help="vfats = list of VFAT numbers (0-23)")
    parser.add_argument("-i", "--iref", action="store", dest="iref_file", help="iref = IREF DAC configuration file ")
    parser.add_argument("-w", "--vref", action="store", dest="vref_file", help="vref = VREF DAC configuration file ")
    args = parser.parse_args()

    if args.system == "chc":
        #print ("Using Rpi CHeeseCake for DAC scan")
        print (Colors.YELLOW + "Only Backend or dryrun supported" + Colors.ENDC)
        sys.exit()
    elif args.system == "backend":
        print ("Using Backend")
        #print ("Only chc (Rpi Cheesecake) or dryrun supported at the moment")
        #sys.exit()
    elif args.system == "dongle":
        #print ("Using USB Dongle for DAC scan")
        print (Colors.YELLOW + "Only Backend or dryrun supported" + Colors.ENDC)
        sys.exit()
    elif args.system == "dryrun":
        print ("Dry Run - not actually running DAC scan")
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
    if args.vfats[0]=='all':
        vfat_list = range(24)
    else:
        for v in args.vfats:
            v_int = int(v)
            if v_int not in range(0,24):
                print (Colors.YELLOW + "Invalid VFAT number, only allowed 0-23" + Colors.ENDC)
                sys.exit()
            vfat_list.append(v_int)

    if args.iref_file is None:
        print (Colors.YELLOW + "Enter IREF DAC configuration file" + Colors.ENDC)
        sys.exit()
    else:
        print('Parsing IREF file...')
        irefs = read_txt_config(args.iref_file)
    
    if args.vref_file is None:
        print (Colors.YELLOW + "Enter VREF DAC configuration file" + Colors.ENDC)
        sys.exit()
    else:
        print('Parsing VREF file...')
        vrefs = read_txt_config(args.vref_file)

    # Parsing Registers XML File
    print("Parsing xml file...")
    parseXML()
    print("Parsing complete...")

    # Initialization (for CHeeseCake: reset and config_select)
    rw_initialize(args.system)
    print("Initialization Done\n")
    
    # Running Phase Scan
    try:
        lpgbt_vfat_set_dac_calibration(args.system, int(args.ohid), vfat_list, irefs, vrefs)
    except KeyboardInterrupt:
        print (Colors.RED + "Keyboard Interrupt encountered" + Colors.ENDC)
        rw_terminate()
    except EOFError:
        print (Colors.RED + "\nEOF Error" + Colors.ENDC)
        rw_terminate()

    # Termination
    rw_terminate()




