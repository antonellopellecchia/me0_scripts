from rw_reg_lpgbt import *
from time import sleep, time
import sys
import argparse
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
        
def lpgbt_communication_test(system, oh_select, vfat_list, depth):
    print ("LPGBT VFAT Communication Check depth=%s transactions" % (str(depth)))
    
    vfat_oh_link_reset()
    cfg_run = 24*[0]
    for vfat in vfat_list:
        lpgbt, gbt_select, elink, gpio = vfat_to_gbt_elink_gpio(vfat)
           
        check_lpgbt_link_ready(oh_select, gbt_select)
        cfg_node = get_rwreg_node('GEM_AMC.OH.OH%d.GEB.VFAT%d.CFG_RUN' % (oh_select, vfat))
        for iread in range(depth):
            vfat_cfg_run = read_backend_reg(cfg_node)
            cfg_run[vfat] += (vfat_cfg_run != 0 and vfat_cfg_run != 1)
        print ("\nVFAT#%02d: reads=%d, errs=%d" % (vfat, depth, cfg_run[vfat]))
    print ("")

def lpgbt_phase_scan(system, oh_select, daq_err, vfat_list, depth, best_phase):
    print ("LPGBT Phase Scan depth=%s transactions" % (str(depth)))

    link_good    = [[0 for phase in range(16)] for vfat in range(24)]
    sync_err_cnt = [[0 for phase in range(16)] for vfat in range(24)]
    cfg_run      = [[0 for phase in range(16)] for vfat in range(24)]
    daq_crc_error      = [[0 for phase in range(16)] for vfat in range(24)]
    errs         = [[0 for phase in range(16)] for vfat in range(24)]

    for vfat in vfat_list:
        lpgbt, gbt_select, elink, gpio = vfat_to_gbt_elink_gpio(vfat)
        check_lpgbt_link_ready(oh_select, gbt_select)

        #print("Configuring VFAT %d" % (vfat))
        #hwid_node = get_rwreg_node("GEM_AMC.OH.OH%d.GEB.VFAT%d.HW_ID" % (oh_select, vfat))
        #output = simple_read_backend_reg(hwid_node, -9999)
        #if output == -9999:
        #    setVfatRxPhase(system, oh_select, vfat, 6)
        #    output = simple_read_backend_reg(hwid_node, -9999)
        #    if output == -9999:
        #        setVfatRxPhase(system, oh_select, vfat, 12)
        #        output = simple_read_backend_reg(hwid_node, -9999)
        #        if output == -9999:
        #            setVfatRxPhase(system, oh_select, vfat, 0)
        #            print (Colors.RED + "Cannot configure VFAT %d"%(vfat) + Colors.ENDC)
        #            rw_terminate()
        #configureVfat(1, vfat, oh_select, 0)
        #for i in range(128):
        #    enableVfatchannel(vfat, oh_select, i, 0, 0) # unmask all channels and disable calpulsing
        #write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_RUN"%(oh_select,vfat)), 0)

    cyclic_running_node = get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_RUNNING")

    for phase in range(0, 16):
        print('Scanning phase %d' % phase)

        # set phases for all vfats under test
        for vfat in vfat_list:
            setVfatRxPhase(system, oh_select, vfat, phase)

        # Configure TTC Generator
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.ENABLE"), 1)
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_GAP"), 500) # 80 kHz
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_CALPULSE_TO_L1A_GAP"), 0) # Disable Calpulse
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_L1A_COUNT"), 10000)

        # read cfg_run some number of times, check link good status and sync errors
        print ("Checking errors: ")
        for vfat in vfat_list:
            lpgbt, gbt_select, elink, gpio = vfat_to_gbt_elink_gpio(vfat)
            # Reset the link, give some time to accumulate any sync errors and then check VFAT comms
            sleep(0.1)
            vfat_oh_link_reset()
            sleep(0.1)

            # Check Slow Control
            cfg_node = get_rwreg_node("GEM_AMC.OH.OH%d.GEB.VFAT%d.CFG_RUN" % (oh_select, vfat))
            for iread in range(depth):
                vfat_cfg_run = simple_read_backend_reg(cfg_node, 9999)
                cfg_run[vfat][phase] += (vfat_cfg_run != 0 and vfat_cfg_run != 1)

            # Check Link Good and Sync Errors
            link_node = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.LINK_GOOD" % (oh_select, vfat))
            sync_node = get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.SYNC_ERR_CNT" % (oh_select, vfat))
            link_good[vfat][phase]    = simple_read_backend_reg(link_node, 0)
            sync_err_cnt[vfat][phase] = simple_read_backend_reg(sync_node, 9999)

            daq_crc_error[vfat][phase] = -1
            # Check DAQ event counter and CRC errors with L1A if link and slow control good
            if daq_err:
                if system == "dryrun" or (link_good[vfat][phase]==1 and sync_err_cnt[vfat][phase]==0 and cfg_run[vfat][phase]==0):
                    # configureVfat(1, vfat, oh_select, 1) # configure VFAT with low threshold
                    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_THR_ARM_DAC"%(oh_select,vfat)), 0) # low threshold for random data
                    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_RUN"%(oh_select,vfat)), 1)
                    for i in range(128):
                        enableVfatchannel(vfat, oh_select, i, 0, 0) # unmask all channels and disable calpulsing

                    # Send L1A to get DAQ events from VFATs
                    write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.CYCLIC_START"), 1)
                    cyclic_running = 1
                    while cyclic_running:
                        cyclic_running = read_backend_reg(cyclic_running_node)

                    daq_event_counter = read_backend_reg(get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.DAQ_EVENT_CNT" % (oh_select, vfat)))
                    if system == "dryrun":
                        daq_crc_error[vfat][phase] = read_backend_reg(get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.DAQ_CRC_ERROR_CNT" % (oh_select, vfat)))
                    else:
                        if daq_event_counter == 10000%(2**16):
                            daq_crc_error[vfat][phase] = read_backend_reg(get_rwreg_node("GEM_AMC.OH_LINKS.OH%d.VFAT%d.DAQ_CRC_ERROR_CNT" % (oh_select, vfat)))
                        else:
                            print (Colors.YELLOW + "\tProblem with DAQ event counter=%d"%(daq_event_counter) + Colors.ENDC)
                    write_backend_reg(get_rwreg_node("GEM_AMC.OH.OH%i.GEB.VFAT%i.CFG_RUN"%(oh_select,vfat)), 0)
            else:
                daq_crc_error[vfat][phase]=0

            result_str = ""
            if link_good[vfat][phase]==1 and sync_err_cnt[vfat][phase]==0 and cfg_run[vfat][phase]==0 and daq_crc_error[vfat][phase]==0:
                result_str += Colors.GREEN
            else:
                result_str += Colors.RED
            if daq_err:
                result_str += "\tResults of VFAT#%02d: link_good=%d, sync_err_cnt=%d, cfg_run_errs=%d, daq_crc_errors=%d" % (vfat, link_good[vfat][phase], sync_err_cnt[vfat][phase], cfg_run[vfat][phase], daq_crc_error[vfat][phase])
            else:
                result_str += "\tResults of VFAT#%02d: link_good=%d, sync_err_cnt=%d, cfg_run_errs=%d" % (vfat, link_good[vfat][phase], sync_err_cnt[vfat][phase], cfg_run[vfat][phase])
            result_str += Colors.ENDC
            print(result_str)
        write_backend_reg(get_rwreg_node("GEM_AMC.TTC.GENERATOR.RESET"), 1)

    centers = 24*[0]
    widths  = 24*[0]

    for vfat in vfat_list:
        for phase in range(0, 16):
            errs[vfat][phase] = (not 1==link_good[vfat][phase]) + sync_err_cnt[vfat][phase] + cfg_run[vfat][phase] + daq_crc_error[vfat][phase]
        centers[vfat], widths[vfat] = find_phase_center(errs[vfat])

    print ("\nphase : 0123456789ABCDEF")
    bestphase_vfat = 24*[0]
    for vfat in vfat_list:
        sys.stdout.write("VFAT%02d: " % (vfat))
        for phase in range(0, 16):

            if (widths[vfat]>0 and phase==centers[vfat]):
                char=Colors.GREEN + "+" + Colors.ENDC
                bestphase_vfat[vfat] = phase
            elif (errs[vfat][phase]):
                char=Colors.RED + "-" + Colors.ENDC
            else:
                char = Colors.YELLOW + "x" + Colors.ENDC

            sys.stdout.write("%s" % char)
            sys.stdout.flush()
        if widths[vfat]<3:
            sys.stdout.write(Colors.RED + " (center=%d, width=%d) BAD\n" % (centers[vfat], widths[vfat]) + Colors.ENDC)
        elif widths[vfat]<5:
            sys.stdout.write(Colors.YELLOW + " (center=%d, width=%d) WARNING\n" % (centers[vfat], widths[vfat]) + Colors.ENDC)
        else:
            sys.stdout.write(Colors.GREEN + " (center=%d, width=%d) GOOD\n" % (centers[vfat], widths[vfat]) + Colors.ENDC)
        sys.stdout.flush()

    # set phases for all vfats under test
    print ("\nSetting all VFAT phases to best phases: ")
    for vfat in vfat_list:
        set_bestphase = 0
        if best_phase is None:
            set_bestphase = bestphase_vfat[vfat]
        else:
            set_bestphase = int(best_phase,16)
        setVfatRxPhase(system, oh_select, vfat, set_bestphase)
        print ("Phase set for VFAT#%02d to: %s" % (vfat, hex(set_bestphase)))
    sleep(0.1)
    vfat_oh_link_reset()
    print ("")

    # Unconfigure VFATs
    #for vfat in vfat_list:
    #    print("Unconfiguring VFAT %d" % (vfat))
    #    configureVfat(0, vfat, oh_select, 0)

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

def setVfatRxPhase(system, oh_select, vfat, phase):

    print ("Setting RX phase %s for VFAT%d" %(hex(phase), vfat))
    lpgbt, gbt_select, elink, gpio = vfat_to_gbt_elink_gpio(vfat)

    if lpgbt == "boss":
        config = config_boss
    elif lpgbt == "sub":
        config = config_sub
    
    # set phase
    GBT_ELINK_SAMPLE_PHASE_BASE_REG = 0x0CC
    addr = GBT_ELINK_SAMPLE_PHASE_BASE_REG + elink
    value = (config[addr] & 0x0f) | (phase << 4)
    
    check_lpgbt_link_ready(oh_select, gbt_select)
    select_ic_link(oh_select, gbt_select)
    if system!= "dryrun" and system!= "backend":
        check_rom_readback()
    mpoke(addr, value)
    sleep(0.000001) # writing too fast for CVP13
    
def test_find_phase_center():
    def check_finder(center, width, errs):
        if (center,width) == find_phase_center(errs):
            print ("OK")
        else:
            print ("FAIL")
    check_finder (5, 5,  [1,1,1,0,0,0,0,0,1,1,0,0,1,1,1,1]) # normal window
    check_finder (3, 4,  [1,0,0,0,0,1,1,1,1,1,0,0,0,1,1,1]) # symmetric goes to higher number (arbitrary)
    check_finder (0, 5,  [0,0,0,1,1,1,1,0,0,0,0,1,1,1,0,0]) # wraparound
    check_finder (3, 4,  [2,0,0,0,0,1,1,1,0,0,0,1,1,1,1,1]) # offset right
    check_finder (2, 4,  [1,0,0,0,0,2,1,1,0,0,0,1,1,1,1,1]) # offset left
    check_finder (0, 0,  [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]) # all bad (default to zero)
    check_finder (7, 16, [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]) # all good, pick the center (arbitrary)

if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='LpGBT Phase Scan')
    parser.add_argument("-s", "--system", action="store", dest="system", help="system = backend or dryrun")
    #parser.add_argument("-l", "--lpgbt", action="store", dest="lpgbt", help="lpgbt = boss or sub")
    parser.add_argument("-o", "--ohid", action="store", dest="ohid", help="ohid = 0-1")
    #parser.add_argument("-g", "--gbtid", action="store", dest="gbtid", help="gbtid = 0-7 (only needed for backend)")
    parser.add_argument("-v", "--vfats", action="store", nargs='+', dest="vfats", help="vfats = list of VFAT numbers (0-23)")
    parser.add_argument("-c", "--daq_err", action="store_true", dest="daq_err", help="if you want to check for DAQ CRC errors")
    parser.add_argument("-d", "--depth", action="store", dest="depth", default="1000", help="depth = number of times to check for cfg_run error")
    parser.add_argument("-b", "--bestphase", action="store", dest="bestphase", help="bestphase = Best value of the elinkRX phase (in hex), calculated from phase scan by default")
    parser.add_argument("-t", "--test", action="store", dest="test", default="0", help="test = enter 1 for only testing vfat communication, default is 0")
    parser.add_argument("-a", "--addr", action="store", nargs='+', dest="addr", help="addr = list of VFATs to enable HDLC addressing")
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
        print ("Dry Run - not actually running phase scan")
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
    
    if args.test not in ["0", "1"]:
        print (Colors.YELLOW + "Test option can only be 0 or 1" + Colors.ENDC)
        sys.exit()

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
        if args.test == "1":
            lpgbt_communication_test(args.system, int(args.ohid), vfat_list, int(args.depth))
        else:
            lpgbt_phase_scan(args.system, int(args.ohid), args.daq_err, vfat_list, int(args.depth), args.bestphase)
    except KeyboardInterrupt:
        print (Colors.RED + "Keyboard Interrupt encountered" + Colors.ENDC)
        rw_terminate()
    except EOFError:
        print (Colors.RED + "\nEOF Error" + Colors.ENDC)
        rw_terminate()

    # Termination
    rw_terminate()




