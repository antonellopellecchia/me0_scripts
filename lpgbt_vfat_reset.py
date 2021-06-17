from rw_reg_lpgbt import *
from time import sleep, time
import sys
import argparse

# VFAT number: boss/sub, ohid, gbtid, elink
# For GE2/1 GEB + Pizza
VFAT_TO_GPIO_GE21 = {
        0  : ("sub"  , 0, 1, 10),
        1  : ("sub"  , 0, 1, 9),
        2  : ("sub"  , 0, 1, 11),
        3  : ("boss" , 0, 0, 0),
        4  : ("boss" , 0, 0, 2),
        5  : ("boss" , 0, 0, 8),
        6  : ("boss" , 1, 0, 0),
        7  : ("boss" , 1, 0, 8),
        8  : ("sub"  , 1, 1, 9),
        9  : ("boss" , 1, 0, 2),
        10 : ("sub"  , 1, 1, 10),
        11 : ("sub"  , 1, 1, 11)
}

# For ME0 GEB
VFAT_TO_GPIO_ME0 = {
        0  : ("sub"  , 0, 1, 10),
        1  : ("sub"  , 0, 1, 9),
        2  : ("sub"  , 0, 1, 11),
        3  : ("boss" , 0, 0, 0),
        4  : ("boss" , 0, 0, 2),
        5  : ("boss" , 0, 0, 8),
        6  : ("sub"  , 1, 1, 10),
        7  : ("sub"  , 1, 1, 9),
        8  : ("sub"  , 1, 1, 11),
        9  : ("boss" , 1, 0, 0),
        10  : ("boss" , 1, 0, 2),
        11  : ("boss" , 1, 0, 8),
}

VFAT_TO_GPIO = VFAT_TO_GPIO_ME0

def vfat_to_oh_gbt_gpio(vfat):
    lpgbt = VFAT_TO_GPIO[vfat][0]
    ohid  = VFAT_TO_GPIO[vfat][1]
    gbtid = VFAT_TO_GPIO[vfat][2]
    gpio = VFAT_TO_GPIO[vfat][3]
    return lpgbt, ohid, gbtid, gpio
        
def convert_gpio_reg(gpio):
    reg_data = 0
    if gpio<=7:
        bit = gpio
    else:
        bit = gpio - 8
    reg_data |= (0x01 << bit)
    return reg_data
        
def lpgbt_vfat_reset(system, vfat_list):
    print ("LPGBT VFAT RESET\n")
    
    gpio_dirH_addr = 0x052
    gpio_dirL_addr = 0x053
    gpio_outH_addr = 0x054
    gpio_outL_addr = 0x055
    gpio_dirH_node = getNode("LPGBT.RWF.PIO.PIODIRH")
    gpio_dirL_node = getNode("LPGBT.RWF.PIO.PIODIRL")
    gpio_outH_node = getNode("LPGBT.RWF.PIO.PIOOUTH")
    gpio_outL_node = getNode("LPGBT.RWF.PIO.PIOOUTL")

    for vfat in vfat_list:
        lpgbt, oh_select, gbt_select, gpio = vfat_to_oh_gbt_gpio(vfat)
        print ("VFAT#: %02d, lpGBT: %s, OH: %d, GBT: %d, GPIO: %d" %(vfat, lpgbt, oh_select, gbt_select, gpio))
        
        boss=0
        if lpgbt=="boss":
            boss=1
        
        if system=="backend":
            check_lpgbt_link_ready(oh_select, gbt_select)
            select_ic_link(oh_select, gbt_select)
        elif system=="chc":
            config_initialize_chc(boss)
            check_lpgbt_ready()
                     
        if system!="dryrun" and system!="backend":
            check_rom_readback()

        # Set GPIO as output
        gpio_dirH_output = 0
        gpio_dirL_output = 0
        if boss:
            gpio_dirH_output = 0x80 | 0x01
            gpio_dirL_output = 0x01 | 0x04
        else:
            gpio_dirH_output = 0x02 | 0x04 | 0x08
            gpio_dirL_output = 0x00
        if system=="backend":
            mpoke(gpio_dirH_addr, gpio_dirH_output)
            mpoke(gpio_dirL_addr, gpio_dirL_output)
        else:
            writeReg(gpio_dirH_node, gpio_dirH_output, 0)
            writeReg(gpio_dirL_node, gpio_dirL_output, 0)

        print ("Set GPIO as output (including GPIO 15 for boss lpGBT), register: 0x%03X, value: 0x%02X" %(gpio_dirH_addr, gpio_dirH_output))
        print ("Set GPIO as output, register: 0x%03X, value: 0x%02X" %(gpio_dirL_addr, gpio_dirL_output))
        sleep(0.000001)

        data_enable = convert_gpio_reg(gpio)
        data_disable = 0x00
        gpio_out_addr = 0
        gpio_out_node = ""
        if gpio<=7:
            gpio_out_addr = gpio_outL_addr
            gpio_out_node = gpio_outL_node
        else:
            gpio_out_addr = gpio_outH_addr
            gpio_out_node = gpio_outH_node
            if boss:
                data_enable |= 0x80 # To keep GPIO LED on ASIAGO ON
                data_disable |= 0x80 # To keep GPIO LED on ASIAGO ON

        # Reset - 1
        if system=="backend":
            mpoke(gpio_out_addr, data_enable)
        else:
            writeReg(gpio_out_node, data_enable, 0)
        print ("Enable GPIO to reset (including GPIO 15 for boss lpGBT), register: 0x%03X, value: 0x%02X" %(gpio_out_addr, data_enable))
        sleep(0.000001) 
            
        # Reset - 0
        if system=="backend":
            mpoke(gpio_out_addr, data_disable)
        else:
            writeReg(gpio_out_node, data_disable, 0)
        print ("Disable GPIO (except GPIO 15 for boss lpGBT), register: 0x%03X, value: 0x%02X" %(gpio_out_addr, data_disable))
        sleep(0.000001) 
        
        print ("")
        
    # Link reset after VFAT reset
    vfat_oh_link_reset()
    sleep(0.1)
    
if __name__ == '__main__':

    # Parsing arguments
    parser = argparse.ArgumentParser(description='lpGBT VFAT RESET')
    parser.add_argument("-s", "--system", action="store", dest="system", help="system = chc, backend or dryrun")
    #parser.add_argument("-l", "--lpgbt", action="store", dest="lpgbt", help="lpgbt = boss or sub")
    parser.add_argument("-v", "--vfats", action="store", dest="vfats", nargs='+', help="vfats = list of VFATs (0-11)")
    #parser.add_argument("-o", "--ohid", action="store", dest="ohid", help="ohid = 0-7 (only needed for backend)")
    #parser.add_argument("-g", "--gbtid", action="store", dest="gbtid", help="gbtid = 0, 1 (only needed for backend)")
    parser.add_argument("-a", "--addr", action="store_true", dest="addr", help="if plugin card addressing needs should be enabled")
    args = parser.parse_args()

    if args.system == "chc":
        print ("Using Rpi CHeeseCake for VFAT reset")
    elif args.system == "backend":
        print ("Using Backend for VFAT reset")
        #print ("Only chc (Rpi Cheesecake) or dryrun supported at the moment")
        #sys.exit()
    elif args.system == "dongle":
        #print ("Using USB Dongle for VFAT reset")
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
        lpgbt_vfat_reset(args.system, vfat_list)
    except KeyboardInterrupt:
        print (Colors.RED + "Keyboard Interrupt encountered" + Colors.ENDC)
        rw_terminate()
    except EOFError:
        print (Colors.RED + "\nEOF Error" + Colors.ENDC)
        rw_terminate()

    # Termination
    rw_terminate()




