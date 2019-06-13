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
import logging
from datetime import datetime

from tomo_scan_lib import *
from dm_lib import *

global variableDict

variableDict = {'PreDarkImages': 0,
        'PreWhiteImages': 0,
        'Projections': 20,
        'PostDarkImages': 10,
        'PostWhiteImages': 10,
        'SampleXOut': 0.0,
        'SampleYOut': 0.0,
        'SampleZOut': 0.0,
#       'SampleRotOut': 0.0,
        'SampleXIn': 0.0,
        'SampleYIn': 0.0,
        'SampleZIn': 0.0,
        'SampleStartPos': 0.0,
        'SampleEndPos': 20.0,
        'StartSleep_min': 0,
        'StabilizeSleep_ms': 0,
        'ExposureTime': 0.2,
        'ExposureTime_flat': 0.2,
        'ShutterOpenDelay': 0.00,
        'IOC_Prefix': '32idcPG3:',
        'ExternalShutter': 0,
        'FileWriteMode': 'Stream',
        'UseInterferometer': 0,
        'nLoops': 1,
        'CCD_Readout': 0.05,
        'RemoteAnalysisDir': 'usr32idc@txmtwo:/local/dataraid/'
        }


global_PVs = {}

def getVariableDict():
    global variableDict
    return variableDict

def get_calculated_num_projections(variableDict):
    info(' ')
    info('  *** get_calculated_num_projections')
    delta = abs((float(variableDict['SampleEndPos']) - float(variableDict['SampleStartPos'])) / (float(variableDict['Projections'])))
    slew_speed = (float(variableDict['SampleEndPos']) - float(variableDict['SampleStartPos'])) / (float(variableDict['Projections']) * (float(variableDict['ExposureTime']) + float(variableDict['CCD_Readout'])))
    info('  *** *** start pos %f' % float(variableDict['SampleStartPos']))
    info('  *** *** end pos %f' % float(variableDict['SampleEndPos']))
    global_PVs['Fly_StartPos'].put(float(variableDict['SampleStartPos']), wait=True)
    global_PVs['Fly_EndPos'].put(float(variableDict['SampleEndPos']), wait=True)
    global_PVs['Fly_SlewSpeed'].put(slew_speed, wait=True)
    global_PVs['Fly_ScanDelta'].put(delta, wait=True)
    time.sleep(3.0)
    calc_num_proj = global_PVs['Fly_Calc_Projections'].get()
    info('  *** *** calculated number of projections: %f' % calc_num_proj)
    if calc_num_proj == None:
        error('  *** *** Error getting fly calculated number of projections!')
        calc_num_proj = global_PVs['Fly_Calc_Projections'].get()
    if calc_num_proj != int(variableDict['Projections']):
        warning('  *** *** updating number of projections from: %d to %d' % (variableDict['Projections'], calc_num_proj))
        variableDict['Projections'] = int(calc_num_proj)
    info('  *** *** Number of projections: %d' % int(variableDict['Projections']))
    info('  *** *** Fly calc triggers: %d' % int(calc_num_proj))
    info('  *** get_calculated_num_projections: Done!')

def fly_scan(variableDict):
    theta = []
    FlyScanTimeout = (float(variableDict['Projections']) * (float(variableDict['ExposureTime']) + float(variableDict['CCD_Readout'])) ) + 30
    info(' ')
    info('  *** Fly Scan Time Estimate: %f minutes' % (FlyScanTimeout/60.))
    global_PVs['Reset_Theta'].put(1)
#   global_PVs['Fly_Set_Encoder_Pos'].put(1) # ensure encoder value match motor position -- only for the PIMicos
    global_PVs['Cam1_AcquireTime'].put(float(variableDict['ExposureTime']) )

    #num_images1 = ((float(variableDict['SampleEndPos']) - float(variableDict['SampleStartPos'])) / (delta + 1.0))
    num_images = int(variableDict['Projections'])
    global_PVs['Cam1_FrameType'].put(FrameTypeData, wait=True)
    global_PVs['Cam1_NumImages'].put(num_images, wait=True)
    global_PVs['Cam1_TriggerMode'].put('Overlapped', wait=True)
    # start acquiring
    global_PVs['Cam1_Acquire'].put(DetectorAcquire)
    wait_pv(global_PVs['Cam1_Acquire'], 1)
    # print('Fly')
    info(' ')
    info('  *** Fly Scan: Start!')
    global_PVs['Fly_Run'].put(1, wait=True)
    wait_pv(global_PVs['Fly_Run'], 0)
    # wait for acquire to finish
    # if the fly scan wait times out we should call done on the detector
    if False == wait_pv(global_PVs['Cam1_Acquire'], DetectorIdle, FlyScanTimeout):
        global_PVs['Cam1_Acquire'].put(DetectorIdle)
    # set trigger move to internal for post dark and white
    #global_PVs['Cam1_TriggerMode'].put('Internal')
    info('  *** Fly Scan: Done!')
    global_PVs['Proc_Theta'].put(1)
    #theta_cnt = global_PVs['Theta_Cnt'].get()
    theta = global_PVs['Theta_Array'].get(count=int(variableDict['Projections']))
    return theta


def start_scan(variableDict, global_PVs, detector_filename):
    info(' ')
    info('  *** start_scan')

    def cleanup(signal, frame):
        stop_scan(global_PVs, variableDict)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    if variableDict.has_key('StopTheScan'):
        stop_scan(global_PVs, variableDict)
        return

    get_calculated_num_projections(variableDict)
    global_PVs['Fly_ScanControl'].put('Custom')

    # Start scan sleep in min so min * 60 = sec
    time.sleep(float(variableDict['StartSleep_min']) * 60.0)
    info(' ')
    info('  *** Taxi before starting capture')
    global_PVs['Fly_Taxi'].put(1, wait=True)
    wait_pv(global_PVs['Fly_Taxi'], 0)
    info('  *** Taxi before starting capture: Done!')

    setup_detector(global_PVs, variableDict)
    setup_writer(global_PVs, variableDict, detector_filename)
    if int(variableDict['PreDarkImages']) > 0:
        info(' ')
        info('  *** Pre Dark Fields') 
        close_shutters(global_PVs, variableDict)
        capture_multiple_projections(global_PVs, variableDict, int(variableDict['PreDarkImages']), FrameTypeDark)
        info('  *** Pre Dark Fields: Done!') 
    if int(variableDict['PreWhiteImages']) > 0:
        info(' ')
        info('  *** Pre White Fields')
        global_PVs['Cam1_AcquireTime'].put(float(variableDict['ExposureTime_flat']) )
        open_shutters(global_PVs, variableDict)
        time.sleep(2)
        move_sample_out(global_PVs, variableDict)
        capture_multiple_projections(global_PVs, variableDict, int(variableDict['PreWhiteImages']), FrameTypeWhite)
        global_PVs['Cam1_AcquireTime'].put(float(variableDict['ExposureTime']) )
        info('  *** Pre White Fields: Done!')

    info(' ')
    info('  *** Setting for fly scan')
    move_sample_in(global_PVs, variableDict)
    open_shutters(global_PVs, variableDict)
    disable_smaract(global_PVs, variableDict)
    info('  *** Setting for fly scan: Done!')

    # run fly scan
    theta = fly_scan(variableDict)
    ###wait_pv(global_PVs['HDF1_NumCaptured'], expected_num_cap, 60)
    enable_smaract(global_PVs, variableDict)
    if int(variableDict['PostWhiteImages']) > 0:
        info(' ')
        info('  *** Post White Fields')
        global_PVs['Cam1_AcquireTime'].put(float(variableDict['ExposureTime_flat']) )
        move_sample_out(global_PVs, variableDict)
        capture_multiple_projections(global_PVs, variableDict, int(variableDict['PostWhiteImages']), FrameTypeWhite)
        global_PVs['Cam1_AcquireTime'].put(float(variableDict['ExposureTime']) )
        info('  *** Post White Fields: Done!')
    if int(variableDict['PostDarkImages']) > 0:
        info(' ')
        info('  *** Post Dark Fields') 
        close_shutters(global_PVs, variableDict)
        time.sleep(2)
        capture_multiple_projections(global_PVs, variableDict, int(variableDict['PostDarkImages']), FrameTypeDark)
        info('  *** Post Dark Fields: Done!') 

    info(' ')
    info('  *** Finalizing scan') 
    close_shutters(global_PVs, variableDict)
    time.sleep(0.25)
    wait_pv(global_PVs['HDF1_Capture_RBV'], 0, 600)
    add_theta(global_PVs, variableDict, theta)
    if variableDict.has_key('UseInterferometer') and int(variableDict['UseInterferometer']) > 0:
            interf_zpx = global_PVs['Interfero_ZPX'].get()
            interf_zpy = global_PVs['Interfero_ZPY'].get()
            det_trig_pulses = global_PVs['det_trig_pulses'].get()
            add_interfero_hdf5(global_PVs, variableDict, interf_zpx,interf_zpy, det_trig_pulses)
    global_PVs['Fly_ScanControl'].put('Standard')
    if False == wait_pv(global_PVs['HDF1_Capture'], 0, 10):
        global_PVs['HDF1_Capture'].put(0)
    reset_CCD(global_PVs, variableDict)
    scp(global_PVs, variableDict)
    info('  *** Finalizing scan: Done!') 


def main():
    tic = time.time()
    update_variable_dict(variableDict)
    init_general_PVs(global_PVs, variableDict)
    FileName = global_PVs['HDF1_FileName'].get(as_string=True)
    nLoops = variableDict['nLoops']
#   global_PVs['HDF1_NextFile'].put(0)
    for iLoop in range(0,nLoops):
        info('  *** Starting fly scan %i' % (iLoop+1))
        global_PVs['Motor_SampleRot'].put(0, wait=True, timeout=600.0)
        start_scan(variableDict, global_PVs, FileName)
        info(' ')
        info('  *** Total scan time: %s minutes' % str((time.time() - tic)/60.))
        

if __name__ == '__main__':
    main()
