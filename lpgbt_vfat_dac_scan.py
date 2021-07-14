from rw_reg_lpgbt import *
from time import sleep, time
import sys
import argparse
import random
import datetime

REGISTER_DAC_MONITOR_MAP = {
    "CFG_IREF": 0,
    "CFG_CAL_DAC_I": 1,
    "CFG_BIAS_PRE_I_BIT": 2,
    "CFG_BIAS_PRE_I_BLCC": 3,
    "CFG_BIAS_PRE_I_BSF": 4,
    "CFG_BIAS_SH_I_BFCAS": 5,
    "CFG_BIAS_SH_I_BDIFF": 6,
    "CFG_BIAS_SD_I_BDIFF": 7,
    "CFG_BIAS_SD_I_BFCAS": 8,
    "CFG_BIAS_SD_I_BSF": 9,
    "CFG_BIAS_CFD_DAC_1": 10,
    "CFG_BIAS_CFD_DAC_2": 11,
    "CFG_EN_HYST": 12,
    "Imon CFD Ireflocal": 13, # ??
    "CFG_THR_ARM_DAC": 14,
    "CFG_THR_ZCC_DAC": 15,
    "Imon SLVS Ibias": 16, # ??
    "Vmon BGR": 32, # ??
    "CFG_CAL_DAC_V": 33,
    "CFG_BIAS_PRE_VREF": 34,
    "Vmon Vth Arm": 35, # ?? 14?
    "Vmon Vth ZCC": 36, # ?? 15?
    "V Tsens Int": 37, # ??
    "V Tsens Ext": 38, # ??
    "CFG_VREF_ADC": 39,
    "CFG_MON_GAIN": 40,
    "SLVS Vref": 41 # ??
}

def lpgbt_vfat_dac_scan(system, oh_select, vfat_list, dac_list, lower, upper, step, niter, adc_ref, vref):
    if not os.path.exists("dac_scan_results"):
        os.makedirs("dac_scan_results")
    now = str(datetime.datetime.now())[:16]
    now = now.replace(":", "_")
    now = now.replace(" ", "_")
    foldername = "dac_scan_results/"
    filename = foldername + "vfat_dac_scan_output_" + now + ".txt"
    file_out = open(filename,"w+") # OH number, DAC register name, VFAT number, dac scan point, value
    print ("LPGBT VFAT DAC Scan for VFATs:")
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
        lpgbt, gbt_select, elink, gpio = vfat_to_gbt_elink_gpio(vfat)
        check_lpgbt_link_ready(oh_select, gbt_select)

        link_good_node[vfat] = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.LINK_GOOD" % (oh_select, vfat))
        sync_error_node[vfat] = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.SYNC_ERR_CNT" % (oh_select, vfat))
        link_good = read_backend_reg(link_good_node[vfat])
        sync_err = read_backend_reg(sync_error_node[vfat])
        if system!="dryrun" and (link_good == 0 or sync_err > 0):
            print (Colors.RED + "Link is bad for VFAT# %02d"%(vfat) + Colors.ENDC)
            rw_terminate()

        dac_node[vfat] = {}
        for dac in dac_list:
            if dac in ["CFG_CAL_DAC_I", "CFG_CAL_DAC_V"]:
                dac = "CFG_CAL_DAC"
            dac_node[vfat][dac] = get_rwreg_node("GEM_AMC.OH.OH%d.GEB.VFAT%d.%s" % (oh_select, vfat, dac))
        vfat_cfg_run_node[vfat] = get_rwreg_node("GEM_AMC.OH.OH%d.GEB.VFAT%d.CFG_RUN" % (oh_select, vfat))
        vfat_cfg_calmode_node[vfat] = get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%d.CFG_CAL_MODE" % (oh_select, vfat))
        adc_monitor_select_node[vfat] = get_rwreg_node("GEM_AMC.OH.OH%d.GEB.VFAT%d.CFG_MONITOR_SELECT" % (oh_select, vfat))
        adc0_cached_node[vfat] = get_rwreg_node("GEM_AMC.OH.OH%d.GEB.VFAT%d.ADC0_CACHED" % (oh_select, vfat))
        adc0_update_node[vfat] = get_rwreg_node("GEM_AMC.OH.OH%d.GEB.VFAT%d.ADC0_UPDATE" % (oh_select, vfat))
        adc1_cached_node[vfat] = get_rwreg_node("GEM_AMC.OH.OH%d.GEB.VFAT%d.ADC1_CACHED" % (oh_select, vfat))
        adc1_update_node[vfat] = get_rwreg_node("GEM_AMC.OH.OH%d.GEB.VFAT%d.ADC1_UPDATE" % (oh_select, vfat))

        write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%d.CFG_VREF_ADC" % (oh_select, vfat)) , vref)

        dac_scan_results[vfat] = {}
        for dac in dac_list:
            dac_scan_results[vfat][dac] = {}
            for reg in range(lower,upper+1,step):
                dac_scan_results[vfat][dac][reg] = -9999

    # Loop over VFATs
    for vfat in vfat_list:
        print ("VFAT %02d"%vfat)
        # Loop over DACs
        for dac in dac_list:
            print ("  Scanning DAC: " + dac)

            # Setup DAC Monitor
            write_backend_reg(adc_monitor_select_node[vfat], REGISTER_DAC_MONITOR_MAP[dac])
            if dac=="CFG_CAL_DAC_I":
                write_backend_reg(vfat_cfg_calmode_node[vfat], 0x2)
            else:
                write_backend_reg(vfat_cfg_calmode_node[vfat], 0x1)

            # Set VFAT to Run Mode
            write_backend_reg(vfat_cfg_run_node[vfat], 0x1)

            # Looping over DAC values
            for reg in range(lower,upper+1,step):

                # Set DAC value
                write_backend_reg(dac_node[vfat][dac], reg)

                adc_value = 0
                # Taking average
                for i in range(0,niter):
                    if adc_ref == "internal": # use ADC0
                        adc_update_read = read_backend_reg(adc0_update_node[vfat]) # read/write to this register triggers a cache update
                        sleep(20e-6) # sleep for 20 us
                        adc_value += read_backend_reg(adc0_cached_node[vfat])
                    elif adc_ref == "external": # use ADC1
                        adc_update_read = read_backend_reg(adc1_update_node[vfat]) # read/write to this register triggers a cache update
                        sleep(20e-6) # sleep for 20 us
                        adc_value += read_backend_reg(adc1_cached_node[vfat])
                dac_scan_results[vfat][dac][reg] = adc_value/niter

            # Set VFAT to Sleep Mode
            write_backend_reg(vfat_cfg_run_node[vfat], 0x0)

            # Reset DAC Monitor
            write_backend_reg(adc_monitor_select_node[vfat], 0)

    print ("")
    # Writing results in output file
    for dac in dac_list:
        for vfat in vfat_list:
            for reg in range(lower,upper+1,step):
                file_out.write("%d;%s;%d;%d;%d\n"%(oh_select,dac,vfat,reg,dac_scan_results[vfat][dac][reg]))

    print ("DAC Scan completed\n")
    file_out.close()
if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='LpGBT VFAT DAC Scan')
    parser.add_argument("-s", "--system", action="store", dest="system", help="system = backend or dryrun")
    #parser.add_argument("-l", "--lpgbt", action="store", dest="lpgbt", help="lpgbt = boss or sub")
    parser.add_argument("-o", "--ohid", action="store", dest="ohid", help="ohid = 0-1")
    #parser.add_argument("-g", "--gbtid", action="store", dest="gbtid", help="gbtid = 0-7 (only needed for backend)")
    parser.add_argument("-v", "--vfats", action="store", nargs='+', dest="vfats", help="vfats = list of VFAT numbers (0-23)")
    parser.add_argument("-r", "--regs", action="store", nargs='+', dest="regs", help="DACs to scan")
    parser.add_argument("-ll", "--lower", action="store", dest="lower", default="0", help="lower = Lower limit for DAC scan (default=0)")
    parser.add_argument("-ul", "--upper", action="store", dest="upper", default="255", help="upper = Upper limit for DAC scan (default=255)")
    parser.add_argument("-t", "--step", action="store", dest="step", default="1", help="step = Step size for DAC scan (default=1)")
    parser.add_argument("-n", "--niter", action="store", dest="niter", default="100", help="niter = Number of times to read ADC for averaging (default=100)")
    parser.add_argument("-f", "--ref", action="store", dest="ref", default = "internal", help="ref = ADC reference: internal or external (default=internal)")
    parser.add_argument("-vr", "--vref", action="store", dest="vref", default = "3", help="vref = CFG_VREF_ADC (0-3) (default=3)")
    parser.add_argument("-a", "--addr", action="store", nargs='+', dest="addr", help="addr = list of VFATs to enable HDLC addressing")
    args = parser.parse_args()

    if args.system == "chc":
        #print ("Using Rpi CHeeseCake for DAC scan")
        print (Colors.YELLOW + "Only Backend or dryrun supported" + Colors.ENDC)
        sys.exit()
    elif args.system == "backend":
        print ("Using Backend for DAC scan")
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
    for v in args.vfats:
        v_int = int(v)
        if v_int not in range(0,24):
            print (Colors.YELLOW + "Invalid VFAT number, only allowed 0-23" + Colors.ENDC)
            sys.exit()
        vfat_list.append(v_int)

    if args.regs is None:
        print(Colors.YELLOW + "Need list of Registers to scan" + Colors.ENDC)
        sys.exit()
    for reg in args.regs:
        if reg not in REGISTER_DAC_MONITOR_MAP:
            print(Colors.YELLOW + "Register %s not supported for DAC scan"%reg + Colors.ENDC)
            sys.exit()

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

    if args.ref not in ["internal", "external"]:
        print (Colors.YELLOW + "ADC reference can only be internal or external" + Colors.ENDC)
        sys.exit()

    vref = int(args.vref)
    if vref>3:
        print (Colors.YELLOW + "Allowed VREF: 0-3" + Colors.ENDC)
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
    
    # Running Phase Scan
    try:
        lpgbt_vfat_dac_scan(args.system, int(args.ohid), vfat_list, args.regs, lower, upper, step, int(args.niter), args.ref, vref)
    except KeyboardInterrupt:
        print (Colors.RED + "Keyboard Interrupt encountered" + Colors.ENDC)
        rw_terminate()
    except EOFError:
        print (Colors.RED + "\nEOF Error" + Colors.ENDC)
        rw_terminate()

    # Termination
    rw_terminate()




