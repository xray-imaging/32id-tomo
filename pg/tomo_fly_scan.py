'''
    FlyScan for Sector 32 ID C

'''
import sys
import json
import time
from epics import PV
import h5py
import shutil
import os
import imp
import traceback

import libs.aps32id_lib as aps32id_lib
import libs.scan_lib as scan_lib
import libs.log_lib as log_lib
import libs.dm_lib as dm_lib
from datetime import datetime

global variableDict
#
#variableDict = {'PreDarkImages':1, # continuous fast scan
#        'PreWhiteImages': 20,
#        'Projections': 18000,
#        'PostDarkImages': 0,
#        'PostWhiteImages': 20,
#        'SampleXOut': 0.2,
#        'SampleYOut': 0.0,
#        'SampleZOut': 0.0,
#        'SampleRotOut': 0.0,
#        'SampleXIn': 0.0,
#        'SampleYIn': 0.0,
#        'SampleZIn': 0.0,
#        'SampleStartPos': 0.0,
#        'SampleEndPos': 3240.0,
#        'StartSleep_min': 0,
#        'StabilizeSleep_ms': 0,
#        'ExposureTime': 0.6,
#        'ExposureTime_Flat': 0.6,
#        'IOC_Prefix': '32idcPG3:',
#        'FileWriteMode': 'Stream',
#        'nLoops': 1,
#        'CCD_Readout': 0.01,
#        'RemoteAnalysisDir': 'usr32idc@txmtwo:/local/dataraid/'
#        }

variableDict = {'PreDarkImages':5,
        'PreWhiteImages': 10,
        'Projections': 1500,
        'PostDarkImages': 5,
        'PostWhiteImages': 10,
        'SampleXOut': 0.5,
        'SampleYOut': 0.0,
        'SampleZOut': 0.0,
        'SampleRotOut': 0.0,
        'SampleXIn': 0.0,
        'SampleYIn': 0.0,
        'SampleZIn': 0.0,
        'SampleStartPos': 0.0,
        'SampleEndPos': 180.0,
        'StartSleep_min': 0,
        'StabilizeSleep_ms': 0,
        'ExposureTime': 1.0,
        'ExposureTime_Flat': 1.0,
        'IOC_Prefix': '32idcPG3:',
        'FileWriteMode': 'Stream',
        'nLoops': 1,
        'CCD_Readout': 0.02,
        'RemoteAnalysisDir': 'usr32idc@txmtwo:/local/dataraid/'
        }


global_PVs = {}

def getVariableDict():
    global variableDict
    return variableDict


def main():

    # create logger
    # # python 3.5+ 
    # home = str(pathlib.Path.home())
    home = os.path.expanduser("~")
    logs_home = home + '/logs/'

    # make sure logs directory exists
    if not os.path.exists(logs_home):
        os.makedirs(logs_home)

    lfname = logs_home + datetime.strftime(datetime.now(), "%Y-%m-%d_%H:%M:%S") + '.log'
    log_lib.setup_logger(lfname)

    tic = time.time()
    aps32id_lib.update_variable_dict(variableDict)
    aps32id_lib.init_general_PVs(global_PVs, variableDict)
    FileName = global_PVs['HDF1_FileName'].get(as_string=True)
    nLoops = variableDict['nLoops']
#   global_PVs['HDF1_NextFile'].put(0)
    for iLoop in range(0,nLoops):
        log_lib.info('  *** Starting fly scan %i' % (iLoop+1))
        global_PVs['Motor_SampleRot'].put(variableDict['SampleStartPos'], wait=True, timeout=600.0)
        scan_lib.tomo_fly_scan(variableDict, global_PVs, FileName)
        dm_lib.scp(global_PVs, variableDict)
        log_lib.info(' ')
        log_lib.info('  *** Total scan time: %.2f minutes' % ((time.time() - tic)/60.))
        
if __name__ == '__main__':
    main()
