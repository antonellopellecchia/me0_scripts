import xml.etree.ElementTree as xml
import sys, os, subprocess

DEBUG = True
ADDRESS_TABLE_TOP = './address_table/lpgbt_registers.xml'
nodes = []
system = ""
reg_list_dryrun = {}
for i in range(462):
    reg_list_dryrun[i] = 0x00
n_rw_reg = (0x13C+1) # number of registers in LPGBT rwf + rw block

TOP_NODE_NAME = "LPGBT"

class Node:
    name = ''
    vhdlname = ''
    address = 0x0
    real_address = 0x0
    permission = ''
    mask = 0x0
    lsb_pos = 0x0
    isModule = False
    parent = None
    level = 0
    mode = None

    def __init__(self):
        self.children = []

    def addChild(self, child):
        self.children.append(child)

    def getVhdlName(self):
        return self.name.replace(TOP_NODE_NAME + '.', '').replace('.', '_')

    def output(self):
        print ('Name:',self.name)
        print ('Address:','{0:#010x}'.format(self.address))
        print ('Permission:',self.permission)
        print ('Mask:',self.mask)
        print ('LSB:',self.lsb_pos)
        print ('Module:',self.isModule)
        print ('Parent:',self.parent.name)

class Colors:
    WHITE   = '\033[97m'
    CYAN    = '\033[96m'
    MAGENTA = '\033[95m'
    BLUE    = '\033[94m'
    YELLOW  = '\033[93m'
    GREEN   = '\033[92m'
    RED     = '\033[91m'
    ENDC    = '\033[0m'

def main():
    parseXML()
    print ('Example:')
    random_node = nodes[1]
    random_node.output()
    i=0
    for node in nodes:
        print (i)
        if (i>0):
            node.output()
        i=i+1

    #print (gbt.gbtx_read_register(320))
    #print str(random_node.__class__.__name__)
    #print 'Node:',random_node.name
    #print 'Parent:',random_node.parent.name
    #kids = []
    #getAllChildren(random_node, kids)
    #print len(kids), kids.name

# Functions related to parsing lpgbt_registers.xml
def parseXML(filename = None, num_of_oh = None):
    if filename == None:
        filename = ADDRESS_TABLE_TOP
    print ('Parsing',filename,'...')
    tree = xml.parse(filename)
    root = tree.getroot()[0]
    vars = {}
    makeTree(root,'',0x0,nodes,None,vars,False,num_of_oh)

def makeTree(node,baseName,baseAddress,nodes,parentNode,vars,isGenerated,num_of_oh=None):
    if (isGenerated == None or isGenerated == False) and node.get('generate') is not None and node.get('generate') == 'true':
        if (node.get('generate_idx_var') == 'OH_IDX' and num_of_oh is not None):
            generateSize = num_of_oh
        else:
            generateSize = parseInt(node.get('generate_size'))
        # generateSize = parseInt(node.get('generate_size'))
        generateAddressStep = parseInt(node.get('generate_address_step'))
        generateIdxVar = node.get('generate_idx_var')
        for i in range(0, generateSize):
            vars[generateIdxVar] = i
            #print('generate base_addr = ' + hex(baseAddress + generateAddressStep * i) + ' for node ' + node.get('id'))
            makeTree(node, baseName, baseAddress + generateAddressStep * i, nodes, parentNode, vars, True)
        return
    newNode = Node()
    name = baseName
    if baseName != '': name += '.'
    name += node.get('id')
    name = substituteVars(name, vars)
    newNode.name = name
    address = baseAddress
    if node.get('address') is not None:
        address = baseAddress + parseInt(eval(node.get('address')))
    newNode.address = address
    newNode.real_address = address
    newNode.permission = node.get('permission')
    newNode.mask = parseInt(node.get('mask'))
    newNode.lsb_pos = mask_to_lsb(newNode.mask)
    newNode.isModule = node.get('fw_is_module') is not None and node.get('fw_is_module') == 'true'
    if node.get('mode') is not None:
        newNode.mode = node.get('mode')
    nodes.append(newNode)
    if parentNode is not None:
        parentNode.addChild(newNode)
        newNode.parent = parentNode
        newNode.level = parentNode.level+1
    for child in node:
        makeTree(child,name,address,nodes,newNode,vars,False,num_of_oh)

def getAllChildren(node,kids=[]):
    if node.children==[]:
        kids.append(node)
        return kids
    else:
        for child in node.children:
            getAllChildren(child,kids)

def getNode(nodeName):
    thisnode = next(
        (node for node in nodes if node.name == nodeName),None
    )
    if (thisnode == None):
        print (nodeName)
    return thisnode

def getNodebyID(number):
    return nodes[number]

def getNodeFromAddress(nodeAddress):
    return next((node for node in nodes if node.real_address == nodeAddress),None)

def getNodesContaining(nodeString):
    nodelist = [node for node in nodes if nodeString in node.name]
    if len(nodelist): return nodelist
    else: return None

def getRegsContaining(nodeString):
    nodelist = [node for node in nodes if nodeString in node.name and node.permission is not None and 'r' in node.permission]
    if len(nodelist): return nodelist
    else: return None

# Functions regarding reading/writing registers
def rw_initialize(system_val, boss=None, ohIdx=None, gbtIdx=None):
    global system
    system = system_val
    if system=="chc":
        import rpi_chc
        global gbt_rpi_chc
        gbt_rpi_chc = rpi_chc.rpi_chc()
        if boss is not None:
            config_initialize_chc(boss)    
    elif system=="backend":
        import rw_reg
        global rw_reg
        rw_reg.parseXML()
        if ohIdx is not None and gbtIdx is not None:
            select_ic_link(ohIdx, gbtIdx)

def config_initialize_chc(boss):
    initialize_success = 1
    initialize_success *= gbt_rpi_chc.config_select(boss)
    if initialize_success:
        initialize_success *= gbt_rpi_chc.en_i2c_switch()
    if initialize_success:
        initialize_success *= gbt_rpi_chc.i2c_channel_sel(boss)
    if not initialize_success:
        print(Colors.RED + "ERROR: Problem in initialization" + Colors.ENDC)
        rw_terminate()
            
def select_ic_link(ohIdx, gbtIdx):
    if system=="backend":
        ohIdx = int(ohIdx)
        gbtIdx = int(gbtIdx)
        if ohIdx not in range(0,8) or gbtIdx not in [0,1]:
            print (Colors.RED + "ERROR: Invalid ohIdx or gbtIdx" + Colors.ENDC)
            rw_terminate()
        linkIdx = ohIdx * 2 + gbtIdx
        output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.GBTX_LINK_SELECT'), linkIdx)
        if output=="Bus Error":
            print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
            output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.GBTX_LINK_SELECT'), linkIdx)
            if output=="Bus Error":
                print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
                rw_terminate()
        output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.GBTX_I2C_ADDR'), 0x70)
        if output=="Bus Error":
            print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
            output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.GBTX_I2C_ADDR'), 0x70)
            if output=="Bus Error":
                print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
                rw_terminate()

def check_lpgbt_link_ready(ohIdx, gbtIdx):
    if system=="backend":
        output = rw_reg.readReg(rw_reg.getNode('GEM_AMC.OH_LINKS.OH%s.GBT%s_READY' % (ohIdx, gbtIdx)))
        if output=="Bus Error":
            print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
            output = rw_reg.readReg(rw_reg.getNode('GEM_AMC.OH_LINKS.OH%s.GBT%s_READY' % (ohIdx, gbtIdx)))
            if output=="Bus Error":
                print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
                rw_terminate()
        link_ready = int(output, 16)
        if (link_ready!=1):
            print (Colors.RED + "ERROR: OH lpGBT links are not READY, check fiber connections" + Colors.ENDC)  
            rw_terminate()

def check_lpgbt_ready(ohIdx=None, gbtIdx=None):
    if system!="dryrun":
        pusmstate = readReg(getNode("LPGBT.RO.PUSM.PUSMSTATE"))
        if (pusmstate==18):
            print ("lpGBT status is READY")
        else:
            print (Colors.RED + "ERROR: lpGBT is not READY, configure lpGBT first" + Colors.ENDC)
            rw_terminate()
    if system=="backend":
        if ohIdx is not None and gbtIdx is not None:
            check_lpgbt_link_ready(ohIdx, gbtIdx)
        
def lpgbt_efuse(boss, enable):
    fuse_success = 1
    if boss:
        lpgbt_type = "Boss"
    else:
        lpgbt_type = "Sub"
    if system=="chc":
        fuse_success = gbt_rpi_chc.fuse_arm_disarm(boss, enable)
        if not fuse_success:
            print(Colors.RED + "ERROR: Problem in fusing for: " + lpgbt_type + Colors.ENDC)
            fuse_off = gbt_rpi_chc.fuse_arm_disarm(boss, 0)
            if not fuse_off:
                print (Colors.RED + "ERROR: EFUSE Power cannot be turned OFF for: " + lpgbt_type + Colors.ENDC)
                print (Colors.YELLOW + "Turn OFF 2.5V fusing Power Supply or Switch Immediately for: " + lpgbt_type + Colors.ENDC)
            rw_terminate()

def chc_terminate():
    # Check EFUSE status and disarm EFUSE if necessary
    efuse_success_boss, efuse_status_boss = gbt_rpi_chc.fuse_status(1) # boss
    efuse_success_sub, efuse_status_sub = gbt_rpi_chc.fuse_status(0) # sub
    if efuse_success_boss and efuse_success_sub:
        if (efuse_status_boss):
            print (Colors.YELLOW + "EFUSE for Boss was ARMED for Boss" + Colors.ENDC)
            fuse_off = gbt_rpi_chc.fuse_arm_disarm(1, 0) # boss
            if not fuse_off:
                print (Colors.RED + "ERROR: EFUSE Power cannot be turned OFF for Boss" + Colors.ENDC)
                print (Colors.YELLOW + "Turn OFF 2.5V fusing Power Supply or Switch Immediately for Boss" + Colors.ENDC)
        if (efuse_status_sub):
            print (Colors.YELLOW + "EFUSE for Sub was ARMED for Sub" + Colors.ENDC)
            fuse_off = gbt_rpi_chc.fuse_arm_disarm(0, 0) # sub
            if not fuse_off:
                print (Colors.RED + "ERROR: EFUSE Power cannot be turned OFF for Sub" + Colors.ENDC)
                print (Colors.YELLOW + "Turn OFF 2.5V fusing Power Supply or Switch Immediately for Sub" + Colors.ENDC)
    else:
        print (Colors.RED + "ERROR: Problem in reading EFUSE status" + Colors.ENDC)
        print (Colors.YELLOW + "Turn OFF 2.5V fusing Power Supply or Switch Immediately (if they were ON) for both Boss and Sub" + Colors.ENDC)

    # Terminating RPi
    terminate_success = gbt_rpi_chc.terminate()
    if not terminate_success:
        print(Colors.RED + "ERROR: Problem in RPi_CHC termination" + Colors.ENDC)
        sys.exit()

def rw_terminate():
    if system=="chc":
        chc_terminate()
    sys.exit()

def check_rom_readback():
    romreg=readReg(getNode("LPGBT.RO.ROMREG"))
    if (romreg != 0xA5):
        print (Colors.RED + "ERROR: no communication with LPGBT. ROMREG=0x%x, EXPECT=0x%x" % (romreg, 0xA5) + Colors.ENDC)
        rw_terminate()
    else:
        print ("Successfully read from ROM. I2C communication OK")

def vfat_oh_link_reset():
    if system=="backend":
        output = rw_reg.writeReg(rw_reg.getNode("GEM_AMC.GEM_SYSTEM.CTRL.LINK_RESET"), 0x1)
        if output=="Bus Error":
            print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
            output = rw_reg.writeReg(rw_reg.getNode("GEM_AMC.GEM_SYSTEM.CTRL.LINK_RESET"), 0x1)
            if output=="Bus Error":
                print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
                rw_terminate()

def global_reset():
    if system=="backend":
        output = rw_reg.writeReg(rw_reg.getNode("GEM_AMC.GEM_SYSTEM.CTRL.GLOBAL_RESET"), 0x1)
        if output=="Bus Error":
            print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
            output = rw_reg.writeReg(rw_reg.getNode("GEM_AMC.GEM_SYSTEM.CTRL.GLOBAL_RESET"), 0x1)
            if output=="Bus Error":
                print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
                rw_terminate()

def get_rwreg_node(name):
    if system=="backend":
        return rw_reg.getNode(name)
    else:
        return ""

def simple_read_backend_reg(node, error_value):
    output_value = 0
    if system=="backend":
        output = rw_reg.readReg(node)
        if output != "Bus Error":
            output_value = int(output,16)
        else:
            output_value = error_value
    return output_value

def simple_write_backend_reg(node, data, error_value):
    output_value = 0
    if system=="backend":
        output = rw_reg.writeReg(node, data)
        if output != "Bus Error":
            output_value = 1
        else:
            output_value = error_value
    return output_value

def read_backend_reg(node):
    output = "0x00"
    if system=="backend":
        output = rw_reg.readReg(node)
        if output=="Bus Error":
            print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
            output = rw_reg.readReg(node)
            if output=="Bus Error":
                print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
                rw_terminate()
    return int(output,16)
    
def write_backend_reg(node, data):
    if system=="backend":
        output = rw_reg.writeReg(node, data)
        if output=="Bus Error":
            print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
            output = rw_reg.writeReg(node, data)
            if output=="Bus Error":
                print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
                rw_terminate()
    
def readAddress(address):
    try:
        output = subprocess.check_output("mpeek (" + str(address) + ")" + stderr==subprocess.STDOUT , shell=True)
        value = ''.join(s for s in output if s.isalnum())
    except subprocess.CalledProcessError as e: value = parseError(int(str(e)[-1:]))
    return '{0:#010x}'.format(parseInt(str(value)))

def readRawAddress(raw_address):
    try:
        address = (parseInt(raw_address) << 2)+0x64000000
        return readAddress(address)
    except:
        return 'Error reading address. (rw_reg)'

def mpeek(address):
    if system=="chc":
        success, data = gbt_rpi_chc.lpgbt_read_register(address)
        if success:
            return data
        else:
            print(Colors.RED + "ERROR: Problem in reading register: " + str(hex(address)) + Colors.ENDC)
            rw_terminate()
    elif system=="backend":
        #rw_reg.writeReg(rw_reg.getNode("GEM_AMC.SLOW_CONTROL.IC.READ_WRITE_LENGTH"), 1)
        #output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.ADDRESS'), address)
        #if output=="Bus Error":
        #    print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
        #    output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.ADDRESS'), address)
        #    if output=="Bus Error":
        #        print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
        #        rw_terminate()
        #output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.EXECUTE_READ'), 1)
        #if output=="Bus Error":
        #    print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
        #    output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.EXECUTE_READ'), 1)
        #    if output=="Bus Error":
        #        print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
        #        rw_terminate()
        #output = rw_reg.readReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.READ_DATA'))
        #if output=="Bus Error":
        #    print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
        #    output = rw_reg.readReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.READ_DATA'))
        #    if output=="Bus Error":
        #        print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
        #        rw_terminate()
        #data = int(output, 16)
        #return data
        return reg_list_dryrun[address]
    #elif system=="dongle":
    #    return gbt_dongle.gbtx_read_register(address)
    elif system=="dryrun":
        return reg_list_dryrun[address]
    else:
        print(Colors.RED + "ERROR: Incorrect system" + Colors.ENDC)
        rw_terminate()

def mpoke(address, value):
    global reg_list_dryrun
    if system=="chc":
        success = gbt_rpi_chc.lpgbt_write_register(address, value)
        if not success:
            print(Colors.RED + "ERROR: Problem in writing register: " + str(hex(address)) + Colors.ENDC)
            rw_terminate()
    elif system=="backend":
        output = rw_reg.writeReg(rw_reg.getNode("GEM_AMC.SLOW_CONTROL.IC.READ_WRITE_LENGTH"), 1)
        if output=="Bus Error":
            print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
            output = rw_reg.writeReg(rw_reg.getNode("GEM_AMC.SLOW_CONTROL.IC.READ_WRITE_LENGTH"), 1)
            if output=="Bus Error":
                print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
                rw_terminate()
        output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.ADDRESS'), address)
        if output=="Bus Error":
            print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
            output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.ADDRESS'), address)
            if output=="Bus Error":
                print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
                rw_terminate()
        output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.WRITE_DATA'), value)
        if output=="Bus Error":
            print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
            output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.WRITE_DATA'), value)
            if output=="Bus Error":
                print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
                rw_terminate()
        output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.EXECUTE_WRITE'), 1)
        if output=="Bus Error":
            print (Colors.YELLOW + "ERROR: Bus Error, Trying again" + Colors.ENDC)
            output = rw_reg.writeReg(rw_reg.getNode('GEM_AMC.SLOW_CONTROL.IC.EXECUTE_WRITE'), 1)
            if output=="Bus Error":
                print (Colors.RED + "ERROR: Bus Error" + Colors.ENDC)
                rw_terminate()
        reg_list_dryrun[address] = value
    #elif system=="dongle":
    #    gbt_dongle.gbtx_write_register(address,value)
    elif system=="dryrun":
        reg_list_dryrun[address] = value
    else:
        print(Colors.RED + "ERROR: Incorrect system" + Colors.ENDC)
        rw_terminate()

def readRegStr(reg):
    return '0x%02X'%(readReg(reg))
    #return '{0:#010x}'.format(readReg(reg))

def readReg(reg):
    try:
        address = reg.real_address
    except:
        print ('Reg',reg,'not a Node')
        return
    if 'r' not in reg.permission:
        return 'No read permission!'

    # read
    value = mpeek(address)

    # Apply Mask
    if (reg.mask != 0):
        value = (reg.mask & value) >> reg.lsb_pos

    return value

def displayReg(reg, option=None):
    address = reg.real_address
    if 'r' not in reg.permission:
        return 'No read permission!'
    # mpeek
    value = mpeek(address)
    # Apply Mask
    if reg.mask is not None:
        shift_amount=0
        for bit in reversed('{0:b}'.format(reg.mask)):
            if bit=='0': shift_amount+=1
            else: break
        final_value = (parseInt(str(reg.mask))&parseInt(value)) >> shift_amount
    else: final_value = value
    final_int =  parseInt(str(final_value))

    if option=='hexbin': return hex(address).rstrip('L')+' '+reg.permission+'\t'+tabPad(reg.name,7)+'{0:#010x}'.format(final_int)+' = '+'{0:032b}'.format(final_int)
    else: return hex(address).rstrip('L')+' '+reg.permission+'\t'+tabPad(reg.name,7)+'{0:#010x}'.format(final_int)

def writeReg(reg, value, readback):
    try:
        address = reg.real_address
    except:
        print ('Reg',reg,'not a Node')
        return
    if 'w' not in reg.permission:
        return 'No write permission!'

    if (readback):
        if (value!=readReg(reg)):
            print (Colors.RED + "ERROR: Failed to read back register %s. Expect=0x%x Read=0x%x" % (reg.name, value, readReg(reg)) + Colors.ENDC)
    else:
        # Apply Mask if applicable
        if (reg.mask != 0):
            value = value << reg.lsb_pos
            value = value & reg.mask
            if 'r' in reg.permission:
                value = (value) | (mpeek(address) & ~reg.mask)
        # mpoke
        mpoke(address, value)

def writeandcheckReg(reg, value):
    try:
        address = reg.real_address
    except:
        print ('Reg',reg,'not a Node')
        return
    if 'w' not in reg.permission:
        return 'No write permission!'

    # Apply Mask if applicable
    if (reg.mask != 0):
        value = value << reg.lsb_pos
        value = value & reg.mask
        if 'r' in reg.permission:
            value = (value) | (mpeek(address) & ~reg.mask)
    # mpoke
    mpoke(address, value)

    # Check register value
    if 'r' not in reg.permission:
        return 'No read permission!, cant check'
    value_check = mpeek(address)
    if (reg.mask != 0):
        value_check = (reg.mask & value_check) >> reg.lsb_pos

    check=0
    if value == value_check:
        check=1
    return check

def isValid(address):
    #try: subprocess.check_output('mpeek '+str(address), stderr=subprocess.STDOUT , shell=True)
    #except subprocess.CalledProcessError as e: return False
    return True

def completeReg(string):
    possibleNodes = []
    completions = []
    currentLevel = len([c for c in string if c=='.'])

    possibleNodes = [node for node in nodes if node.name.startswith(string) and node.level == currentLevel]
    if len(possibleNodes)==1:
        if possibleNodes[0].children == []: return [possibleNodes[0].name]
        for n in possibleNodes[0].children:
            completions.append(n.name)
    else:
        for n in possibleNodes:
            completions.append(n.name)
    return completions

def parseError(e):
    if e==1:
        return "Failed to parse address"
    if e==2:
        return "Bus error"
    else:
        return "Unknown error: "+str(e)

def parseInt(s):
    if s is None:
        return None
    string = str(s)
    if string.startswith('0x'):
        return int(string, 16)
    elif string.startswith('0b'):
        return int(string, 2)
    else:
        return int(string)

def substituteVars(string, vars):
    if string is None:
        return string
    ret = string
    for varKey in vars.keys():
        ret = ret.replace('${' + varKey + '}', str(vars[varKey]))
    return ret

def tabPad(s,maxlen):
    return s+"\t"*((8*maxlen-len(s)-1)/8+1)

def mask_to_lsb(mask):
    if mask is None:
        return 0
    if (mask&0x1):
        return 0
    else:
        idx=1
        while (True):
            mask=mask>>1
            if (mask&0x1):
                return idx
            idx = idx+1

def lpgbt_write_config_file(config_file = 'config.txt'):
    f = open(config_file,"w+")
    for i in range (n_rw_reg):
        val =  mpeek(i)
        write_string = "0x%03X  0x%02X\n" % (i, val)
        f.write(write_string)
    f.close()

def lpgbt_dump_config(config_file = 'Loopback_test.txt'):
        #dump configuration to lpGBT - accepts .txt of .xml input
        # Read configuration file
        if(config_file[-4:] == '.xml'):
            tree = ET.parse(config_file)
            root = tree.getroot()
            reg_config = []
            for i in range(0,366):
                reg_config.append([0,0]) # Value / Mask

            for child in root:
                name_signal = child.attrib['name']
                triplicated = child.attrib['triplicated']
                reg_value   = int(child[0].text)
                if(triplicated in ['true', 'True', 'TRUE']) : n=3
                else                                        : n=1
                for i in range(1,n+1):
                    #print(name_signal)
                    #print(triplicated)
                    #print(reg_value)
                    reg_addr = int(child[i].attrib['startAddress'])
                    startbit = int(child[i].attrib['startBitIndex'])
                    endbit   = int(child[i].attrib['lastBitIndex'])
                    mask     = 2**(startbit+1) - 2**(endbit)
                    reg_config[reg_addr][0] = reg_config[reg_addr][0] | (reg_value << startbit)
                    reg_config[reg_addr][1] = reg_config[reg_addr][1] | mask

            for reg_addr in range(0,len(reg_config)):
                value = reg_config[reg_addr][0]
                mask  = reg_config[reg_addr][1]
                if(mask != 0):
                    value = mpeek(reg_addr)
                    value = (value & (~mask)) | value
                    mpoke(reg_addr, value)
        else:
            input_file = open(config_file, 'r')
            for line in input_file.readlines():
                reg_addr = int(line.split()[0],16)
                value = int(line.split()[1],16)
                if reg_addr in range(0x0f0, 0x105): # I2C Masters
                    value = 0x00
                mpoke(reg_addr, value)
            input_file.close()
        print('lpGBT Configuration Done')

if __name__ == '__main__':
    main()
