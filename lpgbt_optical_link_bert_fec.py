from rw_reg_lpgbt import *
from time import time, sleep
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


def check_fec_errors(system, boss, path, opr, ohid, gbtid, runtime, vfat_list, verbose):
    file_out = open("optical_link_bert_fec_test_output.txt", "w")
    print ("Checking FEC Errors for: " + path)
    file_out.write("Checking FEC Errors for: \n" + path)
    fec_errors = 0

    if opr in ["start", "run"]:
        vfat_oh_link_reset()
    sleep(0.1)

    if path == "uplink": # check FEC errors on backend
        if opr != "run" and opr != "read":
            print (Colors.YELLOW + "Only run and read operation allowed for uplink" + Colors.ENDC)
            rw_terminate()

        fec_node = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.GBT%d_FEC_ERR_CNT" % (ohid, gbtid))

        if opr == "read":
            read_fec_errors = read_backend_reg(fec_node)
            read_fec_error_print = ""
            read_fec_error_write = ""
            if read_fec_errors==0:
                read_fec_error_print += Colors.GREEN
            else:
                read_fec_error_print += Colors.RED
            read_fec_error_print += "\nNumber of FEC Errors = %d\n" %(read_fec_errors)
            read_fec_error_write += "\nNumber of FEC Errors = %d\n" %(read_fec_errors)
            read_fec_error_print += Colors.ENDC
            print (read_fec_error_print)
            file_out.write(read_fec_error_write + "\n")
            return

        # Reset the error counters
        node = get_rwreg_node("GEM_AMC.GEM_SYSTEM.CTRL.LINK_RESET")
        write_backend_reg(node, 0x001)

        vfat_node = []
        for vfat in vfat_list:
            vfat_node.append(get_rwreg_node("GEM_AMC.OH.OH%d.GEB.VFAT%d.%s" % (ohid, vfat-6*ohid, "TEST_REG")))
        
        # start error counting loop
        start_fec_errors = read_backend_reg(fec_node)
        print ("Start Error Counting for time = %f minutes" % (runtime))
        file_out.write("Start Error Counting for time = %f minutes\n" % (runtime))
        print ("Starting with number of FEC Errors = %d\n" % (start_fec_errors))
        file_out.write("Starting with number of FEC Errors = %d\n\n" % (start_fec_errors))
        t0 = time()
        time_prev = t0
        
        while ((time()-t0)/60.0) < runtime:
            for v_node in vfat_node:
                data_write = random.randint(0, (2**32 - 1)) # random number to write (32 bit)
                write_backend_reg(v_node, data_write)
                data_read = read_backend_reg(v_node)
                if system=="backend":
                    if data_read!=data_write:
                        print (Colors.RED + "Register value mismatch\n" + Colors.ENDC)
                        file_out.write("Register value mismatch\n\n")
                        rw_terminate()

            time_passed = (time()-time_prev)/60.0
            if time_passed >= 1:
                curr_fec_errors = read_backend_reg(fec_node)
                if verbose:
                    print ("Time passed: %f minutes, number of FEC errors accumulated = %d" % ((time()-t0)/60.0, curr_fec_errors))
                    file_out.write("Time passed: %f minutes, number of FEC errors accumulated = %d\n" % ((time()-t0)/60.0, curr_fec_errors))
                time_prev = time()
        
        end_fec_errors = read_backend_reg(fec_node)
        print ("\nEnd Error Counting with number of FEC Errors = %d\n" %(end_fec_errors))
        file_out.write("\nEnd Error Counting with number of FEC Errors = %d\n\n" %(end_fec_errors))
        fec_errors = end_fec_errors - start_fec_errors
        
    elif path == "downlink": # check FEC errors on lpGBT
        # Enable the counter
        if opr in ["start", "run"]:
            writeReg(getNode("LPGBT.RW.PROCESS_MONITOR.DLDPFECCOUNTERENABLE"), 0x1, 0)
    
        # start error counting loop
        start_fec_errors = lpgbt_fec_error_counter()
        if opr == "run":
            print ("Start Error Counting for time = %f minutes" % (runtime))
            file_out.write("Start Error Counting for time = %f minutes\n" % (runtime))
        if opr in ["start", "run"]:
            print ("Starting with number of FEC Errors = %d\n" % (start_fec_errors))
            file_out.write("Starting with number of FEC Errors = %d\n\n" % (start_fec_errors))
        t0 = time()
        time_prev = t0

        if opr == "run":
            while ((time()-t0)/60.0) < runtime:
                time_passed = (time()-time_prev)/60.0
                if time_passed >= 1:
                    curr_fec_errors = lpgbt_fec_error_counter()
                    if verbose:
                        print ("Time passed: %f minutes, number of FEC errors accumulated = %d" % ((time()-t0)/60.0, curr_fec_errors))
                        file_out.write("Time passed: %f minutes, number of FEC errors accumulated = %d\n" % ((time()-t0)/60.0, curr_fec_errors))
                    time_prev = time()
        
        end_fec_errors = lpgbt_fec_error_counter()
        end_fec_error_print = ""
        end_fec_error_write = ""
        if end_fec_errors==0:
            end_fec_error_print += Colors.GREEN
        else:
            end_fec_error_print += Colors.RED
        if opr == "read":
            end_fec_error_print += "\nNumber of FEC Errors = %d\n" %(end_fec_errors)
            end_fec_error_write += "\nNumber of FEC Errors = %d\n" %(end_fec_errors)
            end_fec_error_print += Colors.ENDC
            print (end_fec_error_print)
            file_out.write(end_fec_error_write + "\n")
        elif opr == "stop":
            end_fec_error_print += "\nEnd Error Counting with number of FEC Errors = %d\n" %(end_fec_errors)
            end_fec_error_write += "\nEnd Error Counting with number of FEC Errors = %d\n" %(end_fec_errors)
            end_fec_error_print += Colors.ENDC
            print (end_fec_error_print)
            file_out.write(end_fec_error_write + "\n")
        elif opr == "run":
            print ("\nEnd Error Counting with number of FEC Errors = %d\n" %(end_fec_errors))
            file_out.write("\nEnd Error Counting with number of FEC Errors = %d\n\n" %(end_fec_errors))
        fec_errors = end_fec_errors - start_fec_errors
        
        # Disable the counter
        if opr in ["run", "stop"]:
            writeReg(getNode("LPGBT.RW.PROCESS_MONITOR.DLDPFECCOUNTERENABLE"), 0x0, 0)

        if opr != "run":
            return

    data_rate=0
    if path=="uplink":
        print ("For Uplink:")
        file_out.write("For Uplink:\n")
        data_rate = 10.24 * 1e9
    elif path=="downlink":
        print ("For Downlink:")
        file_out.write("For Downlink:\n")
        data_rate = 2.56 * 1e9
    ber = float(fec_errors) / (data_rate * runtime * 60)
    ber_ul = 1.0/ (data_rate * runtime * 60)
    ber_str = ""
    if ber!=0:
        ber_str = "= {:.2e}".format(ber)
    else:
        ber_str = "< {:.2e}".format(ber_ul)
    result_string = ""
    result_string_write = ""
    if fec_errors == 0:
        result_string += Colors.GREEN 
    else:
        result_string += Colors.YELLOW
    result_string += "Number of FEC errors in " + str(runtime) + " minutes: " + str(fec_errors) + "\n"
    result_string += "Bit Error Ratio (BER) " + ber_str + Colors.ENDC + "\n"
    result_string_write += "Number of FEC errors in " + str(runtime) + " minutes: " + str(fec_errors) + "\n"
    result_string_write += "Bit Error Ratio (BER) " + ber_str + "\n"
    print (result_string)
    file_out.write(result_string_write + "\n")
    file_out.close()
    
def lpgbt_fec_error_counter():
    error_counter_h = readReg(getNode("LPGBT.RO.FEC.DLDPFECCORRECTIONCOUNT_H"))
    error_counter_l = readReg(getNode("LPGBT.RO.FEC.DLDPFECCORRECTIONCOUNT_L"))
    error_counter = (error_counter_h << 8) | error_counter_l
    return error_counter   
       
       
if __name__ == '__main__':
    # Parsing arguments
    parser = argparse.ArgumentParser(description='LPGBT Bit Error Ratio Test (BERT) using FEC Error Counters')
    parser.add_argument("-s", "--system", action="store", dest="system", help="system = chc or backend or dongle or dryrun")
    parser.add_argument("-l", "--lpgbt", action="store", dest="lpgbt", help="lpgbt = boss/sub")
    parser.add_argument("-o", "--ohid", action="store", dest="ohid", help="ohid = 0-7 (only needed for backend/dryrun)")
    parser.add_argument("-g", "--gbtid", action="store", dest="gbtid", help="gbtid = 0, 1 (only needed for backend/dryrun)")
    parser.add_argument("-p", "--path", action="store", dest="path", help="path = uplink, downlink")
    parser.add_argument("-r", "--opr", action="store", dest="opr", default="run", help="opr = start, run, read, stop (only run, read allowed for uplink)")
    parser.add_argument("-t", "--time", action="store", dest="time", help="TIME = measurement time in minutes")
    parser.add_argument("-v", "--vfats", action="store", dest="vfats", nargs='+', help="vfats = list of VFATs (0-11) for read/write TEST_REG")
    parser.add_argument("-a", "--addr", action="store_true", dest="addr", help="if plugiin card addressing needs should be enabled")
    parser.add_argument("-z", "--verbose", action="store_true", dest="verbose", help="VERBOSE")
    args = parser.parse_args()

    if args.system == "chc":
        print ("Using Rpi CHeeseCake for BERT")
    elif args.system == "backend":
        print ("Using Backend for BERT")
        #print (Colors.YELLOW + "Only chc (Rpi Cheesecake) or dryrun supported at the moment" + Colors.ENDC)
        #sys.exit()
    elif args.system == "dongle":
        #print ("Using USB Dongle for checking configuration")
        print (Colors.YELLOW + "Only chc (Rpi Cheesecake) or dryrun supported at the moment" + Colors.ENDC)
        sys.exit()
    elif args.system == "dryrun":
        print ("Dry Run - not actually running on lpGBT")
    else:
        print (Colors.YELLOW + "Only valid options: chc, backend, dongle, dryrun" + Colors.ENDC)
        sys.exit()

    boss = None
    if args.lpgbt is None:
        print (Colors.YELLOW + "Please select boss/sub" + Colors.ENDC)
        sys.exit()
    elif (args.lpgbt=="boss"):
        print ("BERT for boss LPGBT")
        boss=1
    elif (args.lpgbt=="sub"):
        print ("BERT for sub LPGBT")
        boss=0
    else:
        print (Colors.YELLOW + "Please select boss/sub" + Colors.ENDC)
        sys.exit()
    if boss is None:
        sys.exit()
      
    if args.system == "backend" or args.system == "dryrun":
        if args.ohid is None:
            print (Colors.YELLOW + "Need OHID for backend/dryrun" + Colors.ENDC)
            sys.exit()
        if args.gbtid is None:
            print (Colors.YELLOW + "Need GBTID for backend/dryrun" + Colors.ENDC)
            sys.exit()
        if int(args.ohid)>7:
            print (Colors.YELLOW + "Only OHID 0-7 allowed" + Colors.ENDC)
            sys.exit()
        if int(args.gbtid)>1:
            print (Colors.YELLOW + "Only GBTID 0 and 1 allowed" + Colors.ENDC)
            sys.exit() 
    else:
        if args.ohid is not None or args.gbtid is not None:
            print (Colors.YELLOW + "OHID and GBTID only needed for backend" + Colors.ENDC)
            sys.exit()
        args.ohid = "-9999"
        args.gbtid = "-9999"

    if args.path not in ["uplink", "downlink"]:
        print (Colors.YELLOW + "Enter valid path" + Colors.ENDC)
        sys.exit()

    if args.path == "uplink":
        if args.system == "chc":
            print (Colors.YELLOW + "For uplink, cheesecake not possible" + Colors.ENDC)
            sys.exit()
        if args.opr != "run" and args.opr != "read":
            print (Colors.YELLOW + "For uplink, only run and read operation allowed" + Colors.ENDC)
            sys.exit()
    elif args.path == "downlink":
        if args.opr not in ["start", "run", "read", "stop"]:
            print (Colors.YELLOW + "Invalid operation" + Colors.ENDC)
            sys.exit()

    if not boss:
        if args.path != "uplink":
            print (Colors.YELLOW + "Only uplink can be checked for sub lpGBT" + Colors.ENDC)
            sys.exit()

    if (args.path == "uplink" and args.opr == "run") or (args.path == "downlink" and args.opr == "run"):
        if args.time is None:
            print (Colors.YELLOW + "BERT measurement time required" + Colors.ENDC)
            sys.exit()
    else:
        if args.time is not None:
            print (Colors.YELLOW + "BERT measurement time not required" + Colors.ENDC)
            sys.exit()
        args.time = "0"

    vfat_list = []
    if args.vfats is not None:
        if args.path != "uplink":
            print (Colors.YELLOW + "VFAT only for uplink" + Colors.ENDC)
            sys.exit()
        for v in args.vfats:
            v_int = int(v)
            if v_int not in range(0,12):
                print (Colors.YELLOW + "Invalid VFAT number, only allowed 0-11" + Colors.ENDC)
                sys.exit()
            lpgbt, oh_select, gbt_select, elink = vfat_to_oh_gbt_elink(v_int)
            if lpgbt!=args.lpgbt or oh_select!=int(args.ohid) or gbt_select!=int(args.gbtid):
                print (Colors.YELLOW + "Invalid VFAT number for selected lpGBT" + Colors.ENDC)
                sys.exit()
            vfat_list.append(v_int)

    # Parsing Registers XML File
    print("Parsing xml file...")
    parseXML()
    print("Parsing complete...")

    # Initialization (for CHeeseCake: reset and config_select)
    rw_initialize(args.system, boss, args.ohid, args.gbtid)
    print("Initialization Done\n")

    if args.addr:
        print ("Enabling VFAT addressing for plugin cards")
        write_backend_reg(get_rwreg_node("GEM_AMC.GEM_SYSTEM.VFAT3.USE_VFAT_ADDRESSING"), 1)
    
    # Readback rom register to make sure communication is OK
    if args.system!="dryrun" and args.system!="backend":
        check_rom_readback()

    # Check if lpGBT is READY
    if args.system!="dryrun":
        if args.system=="backend":
            check_lpgbt_link_ready(args.ohid, args.gbtid)
        else:
            check_lpgbt_ready()

    try:
        check_fec_errors(args.system, boss, args.path, args.opr, int(args.ohid), int(args.gbtid), float(args.time), vfat_list, args.verbose)
    except KeyboardInterrupt:
        print (Colors.RED + "\nKeyboard Interrupt encountered" + Colors.ENDC)
        rw_terminate()
    except EOFError:
        print (Colors.RED + "\nEOF Error" + Colors.ENDC)
        rw_terminate()

    # Termination
    rw_terminate()
