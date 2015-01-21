'''
Created on 23/11/2013

@author: Du
'''
import pickle
import struct
import matplotlib.pyplot as plt
import numpy as np
import scipy
from scipy import signal
    
def calculate_heart_rate(data,time):
    '''
    Will calculate heart rate from an array of numbers and timestamps for each number. Based on r-r interval
    '''
    data = scipy.signal.detrend(data)
    
    
    #calculates ALL peaks and finds average from the peaks
    if len(data) != len(time):
        print 'something is clearly wrong. The data should be same size as the time (in calculate_heart_rate)'
    peaks = []
    
    #peak detection
    res = 5
    for i in range(res, len(data)-res):
        if data[i]>data[i-res]+.1 and data[i]>data[i+res]+.1:  
            if data[i]>data[i-1] and data[i]>data[i+1]:  
                peaks.append((data[i],time[i],i)) #(value,time,index)
    
    
    
    r_peaks = []
    #having all peaks now - the filtering begins! All r-peaks have a corresponding t-peak
    for i in range(0,len(peaks),2):
        if (i+1)<len(peaks):
            if peaks[i][0] > peaks[i+1][0]:
                r_peaks.append(peaks[i])
            else:
                r_peaks.append(peaks[i+1])
    
    
    #r_peaks found, calculating heart rate between peaks
    heart_rates = []
    for i in range(0,len(r_peaks)):
        if (i+1)<len(r_peaks):
            #within bounds
            try:
                heart_rate = (1.0/(r_peaks[i+1][1]-r_peaks[i][1]))*60
                if heart_rate < 200 and heart_rate >50:
                    heart_rates.append((heart_rate,r_peaks[i][1],r_peaks[i][2]))
            except:
                print 'division by zero'
    #fill array with heart rates
    heart_rate = []
    if heart_rates == []:
        heart_rate.append(0.0)
    else:
        current_hr = heart_rates[0][0]
        for i in range(len(time)):
            for hr in heart_rates:
                if i==hr[2]:
                    current_hr = hr[0]
                    break
            heart_rate.append(current_hr)
    
    #plot hr
    plt.subplot(2,1,1)
    plt.plot(time,data)
    peak_x = [t for (peak,t,index) in r_peaks]
    peak_y = [peak for (peak,t,index) in r_peaks]
    plt.plot(peak_x,peak_y,'rx')
    plt.ylabel('uV')
    plt.subplot(2,1,2)

    plt.plot(time,heart_rate)
    plt.ylabel('bpm')
    plt.show()
    
    return heart_rate

if __name__ == '__main__':
    file = pickle.load(open('raw_network_input','rb'))
    plet = []
    for sample in file:
        plet.append(struct.unpack('<i', sample[39:42] +('\0' if sample[42] < '\x80' else '\xff'))[0])
    time = [1.0/128.0*i for i in range(len(plet))]
    zipped = zip(plet,time)
    filtered = [(p,t) for (p,t) in zipped if p > 0]
    new_plet, new_time = zip(*filtered)
    print len(new_plet), len(new_time)
    #plt.plot(new_time,new_plet)
    #plt.plot(range(len(plet)),plet)
    #plt.show()
    calculate_heart_rate(new_plet, new_time)
