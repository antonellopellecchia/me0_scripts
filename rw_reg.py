import xml.etree.ElementTree as xml
import sys, os, subprocess
from ctypes import *
from config import *
import imp

print ('Loading shared library: librwreg.so')
lib_DEFAULT = "./lib/librwreg_backup.so"
lib_file = os.environ.get('ME0_LIBRWREG_SO')
if lib_file is None:
    lib_file = lib_DEFAULT
lib = CDLL(lib_file)
rReg = lib.getReg
rReg.restype = c_uint
rReg.argtypes=[c_uint]
wReg = lib.putReg
wReg.restype = c_uint
wReg.argtypes=[c_uint,c_uint]
regInitExists = False
try:
    regInit = lib.rwreg_init
    regInit.argtypes=[c_char_p]
    regInitExists = True
except:
    print("WARNING: rwreg_init() function does not exist.. if you're running on CTP7, you can safely ignore this warning.")

DEBUG = True
ADDRESS_TABLE_DEFAULT = './address_table/gem_amc_backup.xml'
nodes = {}

boardType = os.environ.get('BOARD_TYPE')
if boardType is None:
    boardType = "cvp13"
DEVICE = CONFIG_RWREG[boardType]['DEVICE']
if sys.version_info[0] == 3:
    DEVICE = CONFIG_RWREG[boardType]['DEVICE'].encode()
BASE_ADDR = CONFIG_RWREG[boardType]['BASE_ADDR']

class Node:
    name = ''
    description = ''
    vhdlname = ''
    address = 0x0
    real_address = 0x0
    permission = ''
    mask = 0x0
    isModule = False
    parent = None
    level = 0
    warn_min_value = None
    error_min_value = None

    def __init__(self):
        self.children = []

    def addChild(self, child):
        self.children.append(child)

    def getVhdlName(self):
        return self.name.replace(TOP_NODE_NAME + '.', '').replace('.', '_')

    def output(self):
        print ('Name:',self.name)
        print ('Description:',self.description)
        print ('Address:','{0:#010x}'.format(self.address))
        print ('Permission:',self.permission)
        print ('Mask:','{0:#010x}'.format(self.mask))
        print ('Module:',self.isModule)
        print ('Parent:',self.parent.name)

def main():
    parseXML()
    print ('Example:')
    random_node = nodes["GEM_AMC.GEM_SYSTEM.BOARD_ID"]
    #print (str(random_node.__class__.__name__))
    print ('Node:',random_node.name)
    print ('Parent:',random_node.parent.name)
    kids = []
    getAllChildren(random_node, kids)
    print (len(kids), kids.name)

def parseXML():
    if regInitExists:
        regInit(DEVICE)
    addressTable = os.environ.get('ADDRESS_TABLE')
    if addressTable is None:
        print ('Warning: environment variable ADDRESS_TABLE is not set, using a default of %s' % ADDRESS_TABLE_DEFAULT)
        addressTable = ADDRESS_TABLE_DEFAULT
    print ('Parsing',addressTable,'...')
    tree = None
    lxmlExists = False
    try:
        imp.find_module('lxml')
        import lxml.etree
        lxmlExists = True
    except:
        print("WARNING: lxml python module was not found, so xinclude won't work")

    if lxmlExists:
        tree = lxml.etree.parse(addressTable)
        try:
            tree.xinclude()
        except Exception as e:
            print(e)
    else:
        tree = xml.parse(addressTable)

    root = tree.getroot()
    vars = {}
    makeTree(root,'',0x0,nodes,None,vars,False)

def makeTree(node,baseName,baseAddress,nodes,parentNode,vars,isGenerated):

    if node.get('id') is None:
        return

    if (isGenerated == None or isGenerated == False) and node.get('generate') is not None and node.get('generate') == 'true':
        generateSize = parseInt(node.get('generate_size'))
        generateAddressStep = parseInt(node.get('generate_address_step'))
        generateIdxVar = node.get('generate_idx_var')
        for i in range(0, generateSize):
            vars[generateIdxVar] = i
            makeTree(node, baseName, baseAddress + generateAddressStep * i, nodes, parentNode, vars, True)
        return
    newNode = Node()
    name = baseName
    if baseName != '': name += '.'
    name += node.get('id')
    name = substituteVars(name, vars)
    newNode.name = name
    if node.get('description') is not None:
        newNode.description = node.get('description')
    address = baseAddress
    if node.get('address') is not None:
        address = baseAddress + parseInt(node.get('address'))
    newNode.address = address
    newNode.real_address = (address<<2) + BASE_ADDR
    newNode.permission = node.get('permission')
    newNode.mask = parseInt(node.get('mask'))
    newNode.isModule = node.get('fw_is_module') is not None and node.get('fw_is_module') == 'true'
    if node.get('sw_monitor_warn_min_threshold') is not None:
        newNode.warn_min_value = node.get('sw_monitor_warn_min_threshold')
    if node.get('sw_monitor_error_min_threshold') is not None:
        newNode.error_min_value = node.get('sw_monitor_error_min_threshold')
    nodes[newNode.name] = newNode
    if parentNode is not None:
        parentNode.addChild(newNode)
        newNode.parent = parentNode
        newNode.level = parentNode.level+1
    for child in node:
        makeTree(child,name,address,nodes,newNode,vars,False)


def getAllChildren(node,kids=[]):
    if node.children==[]:
        kids.append(node)
        return kids
    else:
        for child in node.children:
            getAllChildren(child,kids)

def getNode(nodeName):
    thisnode = None
    if nodeName in nodes:
        thisnode = nodes[nodeName]
    if (thisnode == None):
        print (nodeName)
    return thisnode

def getNodeFromAddress(nodeAddress):
    return next((nodes[nodename] for nodename in nodes if nodes[nodename].real_address == nodeAddress),None)

def getNodesContaining(nodeString):
    nodelist = [nodes[nodename] for nodename in nodes if nodeString in nodename]
    if len(nodelist): return nodelist
    else: return None

#returns *readable* registers
def getRegsContaining(nodeString):
    nodelist = [nodes[nodename] for nodename in nodes if nodeString in nodename and nodes[nodename].permission is not None and 'r' in nodes[nodename].permission]
    if len(nodelist): return nodelist
    else: return None

def readAddress(address):
    output = rReg(address)
    return '{0:#010x}'.format(parseInt(str(output)))

def readRawAddress(raw_address):
    try:
        address = (parseInt(raw_address) << 2) + BASE_ADDR
        return readAddress(address)
    except:
        return 'Error reading address. (rw_reg)'

def mpeek(address):
    try:
        output = subprocess.check_output('mpeek '+str(address), stderr=subprocess.STDOUT , shell=True)
        value = ''.join(s for s in output if s.isalnum())
    except subprocess.CalledProcessError as e: value = parseError(int(str(e)[-1:]))
    return value

def mpoke(address,value):
    try: output = subprocess.check_output('mpoke '+str(address)+' '+str(value), stderr=subprocess.STDOUT , shell=True)
    except subprocess.CalledProcessError as e: return parseError(int(str(e)[-1:]))
    return 'Done.'


def readReg(reg):
    address = reg.real_address
    if 'r' not in reg.permission:
        return 'No read permission!'
    value = rReg(parseInt(address))
    if parseInt(value) == 0xdeaddead:
        return 'Bus Error'
    if reg.mask is not None:
        shift_amount=0
        for bit in reversed('{0:b}'.format(reg.mask)):
            if bit=='0': shift_amount+=1
            else: break
        final_value = (parseInt(str(reg.mask))&parseInt(value)) >> shift_amount
    else: final_value = value
    final_int =  parseInt(str(final_value))
    return '{0:#010x}'.format(final_int)

def displayReg(reg,option=None):
    address = reg.real_address
    if 'r' not in reg.permission:
        return 'No read permission!'
    value = rReg(parseInt(address))
    if parseInt(value) == 0xdeaddead:
        if option=='hexbin': return hex(address).rstrip('L')+' '+reg.permission+'\t'+tabPad(reg.name,7)+'Bus Error'
        else: return hex(address).rstrip('L')+' '+reg.permission+'\t'+tabPad(reg.name,7)+'Bus Error'
    if reg.mask is not None:
        shift_amount=0
        for bit in reversed('{0:b}'.format(reg.mask)):
            if bit=='0': shift_amount+=1
            else: break
        final_value = (parseInt(str(reg.mask))&parseInt(value)) >> shift_amount
    else: final_value = value
    final_int =  parseInt(final_value)
    if option=='hexbin': return hex(address).rstrip('L')+' '+reg.permission+'\t'+tabPad(reg.name,7)+'{0:#010x}'.format(final_int)+' = '+'{0:032b}'.format(final_int)
    else: return hex(address).rstrip('L')+' '+reg.permission+'\t'+tabPad(reg.name,7)+'{0:#010x}'.format(final_int)

def writeReg(reg, value):
    address = reg.real_address
    if 'w' not in reg.permission:
        return 'No write permission!'
    # Apply Mask if applicable
    if reg.mask is not None:
        shift_amount=0
        for bit in reversed('{0:b}'.format(reg.mask)):
            if bit=='0': shift_amount+=1
            else: break
        shifted_value = value << shift_amount
        initial_value = readAddress(address)
        try: initial_value = parseInt(initial_value)
        except ValueError: return 'Error reading initial value: '+str(initial_value)
        final_value = (shifted_value & reg.mask) | (initial_value & ~reg.mask)
    else: final_value = value
    output = wReg(parseInt(address),parseInt(final_value))
    if output < 0 or output == 0xffffffffL:
        return 'Bus Error'
    else:
        return str('{0:#010x}'.format(final_value)).rstrip('L')+'('+str(value)+')\twritten to '+reg.name

def isValid(address):
    try: subprocess.check_output('mpeek '+str(address), stderr=subprocess.STDOUT , shell=True)
    except subprocess.CalledProcessError as e: return False
    return True


def completeReg(string):
    possibleNodes = []
    completions = []
    currentLevel = len([c for c in string if c=='.'])

    possibleNodes = [nodes[nodename] for nodename in nodes if nodename.startswith(string) and nodes[nodename].level == currentLevel]
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
        return "My Bus error"
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

if __name__ == '__main__':
    main()
