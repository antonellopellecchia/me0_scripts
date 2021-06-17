from rw_reg_lpgbt import *
from time import sleep, time
import sys
import argparse
import random

        
def lpgbt_vfat_bert(system, oh_select, vfat_list, reg_list, niter, verbose):
    print ("LPGBT VFAT Slow Control Timing Measurements\n" % (str(niter)))
    errors = {}
    error_rates = {}
    link_bad_errors = {}
    sync_errors = {}

    vfat_oh_link_reset()
    sleep(0.1)

    for reg in reg_list:
        print ("Using register: " + reg)
        write_perm = 0
        if vfat_registers[reg] == "r":
            print ("Operation: READ Only\n")
        elif vfat_registers[reg] == "rw":
            print ("Operation: READ & WRITE\n")
            write_perm = 1

        errors[reg] = 24*[0]
        error_rates[reg] = 24*[0]
        link_bad_errors[reg] = 24*[0]
        sync_errors[reg] = 24*[0]

        node = {}
        for vfat in vfat_list:
            lpgbt, gbt_select, elink, gpio = vfat_to_gbt_elink_gpio(vfat)
            print ("VFAT#: %02d" %(vfat))
            
            check_lpgbt_link_ready(oh_select, gbt_select)
            node[vfat] = get_rwreg_node('GEM_AMC.OH.OH%d.GEB.VFAT%d.%s' % (oh_select, vfat, reg))

        #n=0
        #while n<niter:
        #    for vfat in vfat_list:
        #        write_backend_reg(node[vfat], 0x111222)
        #        data_read_after = read_backend_reg(node[vfat])
        #    n+=1

        t0 = time()
        print ("Start time %f microseconds"%((time() - t0)*1e6))
        for vfat in vfat_list:
            n=0
            while n < niter:
                print ("New loop %f microseconds"%((time() - t0)*1e6))
                write_backend_reg(node[vfat], 0x111222)
                print ("Reading done %f microseconds"%((time() - t0)*1e6))
                data_read_after = read_backend_reg(node[vfat])
                print ("Writing done %f microseconds"%((time() - t0)*1e6))
                print ("")
                n+=1

        print ("Stop time %f microseconds"%((time() - t0)*1e6))

        print ("Operations for register %s completed \n" % (reg))      


if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='LpGBT VFAT Slow Control Timing Test')
    parser.add_argument("-s", "--system", action="store", dest="system", help="system = backend or dryrun")
    #parser.add_argument("-l", "--lpgbt", action="store", dest="lpgbt", help="lpgbt = boss or sub")
    parser.add_argument("-o", "--ohid", action="store", dest="ohid", help="ohid = 0-1")
    #parser.add_argument("-g", "--gbtid", action="store", dest="gbtid", help="gbtid = 0-7 (only needed for backend)")
    parser.add_argument("-v", "--vfats", action="store", nargs='+', dest="vfats", help="vfats = list of VFAT numbers (0-23)")
    parser.add_argument("-r", "--reg", action="store", dest="reg", nargs='+', help="reg = register names to read/write: HW_ID (read), HW_ID_VER (read), TEST_REG (read/write), HW_CHIP_ID (read)")
    parser.add_argument("-n", "--niter", action="store", dest="niter", default="1", help="niter = number of times to perform the read/write")
    parser.add_argument("-a", "--addr", action="store", nargs='+', dest="addr", help="addr = list of VFATs to enable HDLC addressing")
    parser.add_argument("-z", "--verbose", action="store_true", dest="verbose", default=False, help="Set for more verbosity")
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

    if args.reg is None:
        print ("Enter list of registers to read/write on VFAT")
        sys.exit()
    else:
        for r in args.reg:
            if r not in vfat_registers:
                print (Colors.YELLOW + "Only valid options: HW_ID (read), HW_ID_VER (read), TEST_REG (read/write), HW_CHIP_ID (read)" + Colors.ENDC)  
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
        lpgbt_vfat_bert(args.system, int(args.ohid), vfat_list, args.reg, int(args.niter), args.verbose)
    except KeyboardInterrupt:
        print (Colors.RED + "Keyboard Interrupt encountered" + Colors.ENDC)
        rw_terminate()
    except EOFError:
        print (Colors.RED + "\nEOF Error" + Colors.ENDC)
        rw_terminate()

    # Termination
    rw_terminate()




