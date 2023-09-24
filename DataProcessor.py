

import numpy as np
import sys
from enum import Enum

class State(Enum):
    NONE = 0
    WASH = 1
    DRY = 2
    BOTH = 3

# "Expert System" classifier for laundry status given current.
class HeuristicSignalProcessor:
    def __init__(self, edge_n=6, spike_n=40, spike_max=200, wash_th=40, dry_th=700, wd_th=1650, idle_time=16,spin_time=100,cal=1.0):
        self.edge_buf = np.zeros((edge_n,1))
        self.peak_buf = np.zeros((3,1))
        self.spike_buf = np.zeros((spike_n))
        self.spike_max = spike_max
        self.wash_th = wash_th
        self.dry_th = dry_th
        self.wd_th = wd_th
        self.wd_count = 0
        self.wiggle_count = 0
        self.null_count = 0
        self.idle_time = idle_time
        self.spin_time = spin_time
        self.spin_done_time = 0
        self.dry_min = 0
        self.cal = cal
        self.state = State.NONE

    def reset(self):
        self.__init__()

    def process_sample(self, sample, only_diff=True):
        self.edge_buf = np.roll(self.edge_buf,1)
        self.peak_buf = np.roll(self.peak_buf,1)
        self.spike_buf = np.roll(self.spike_buf,1)

        sample = sample*self.cal
        self.edge_buf[0] = sample

        self.peak_buf[0] = np.min(self.edge_buf[0:1]) - np.max(self.edge_buf[4:5])
        e = self.peak_buf[0]

        pb = self.peak_buf
        spike = pb[1] * (pb[1] >= pb[2] and pb[1] >= pb[0])
        self.spike_buf[0] = spike * (spike > 0) * (spike < self.spike_max)

        wiggle = sum(self.spike_buf > self.wash_th) >= 3

        if (wiggle):
            self.wiggle_count = 0
        else:
            self.wiggle_count += 1

        new_state = self.state

        # keep track of how long we've been under the wash threshold
        self.null_count = self.null_count + 1 if sample < self.wash_th else 0

        # keep track of how long we've exceeded the wash+dry threshold wd_thresh
        wd_time = 0
        if (sample > self.wd_th):
            self.wd_count += 1
        else:
            wd_time = self.wd_count
            self.wd_count = 0

        if (self.state == State.NONE): # NONE
            if (spike > self.dry_th):
                new_state = State.DRY
            elif (spike > self.wash_th):
                new_state = State.WASH
    
        elif (self.state == State.WASH): # WASH
            if (spike > self.dry_th):
                new_state = State.DRY

        elif (self.state == State.DRY): # DRY
            if sample < self.dry_th:
                new_state = State.NONE
            elif wiggle:
                new_state = State.BOTH
            
        elif (self.state == State.BOTH): # BOTH
            if (sample < self.dry_th):
                new_state = State.WASH
            if (sample < self.wash_th):
                new_state = State.NONE
            if (wd_time > self.spin_time):
                self.spin_done_time = 1
            if (self.spin_done_time and sample < self.wd_th):
                self.spin_done_time += 1
            else:
                self.spin_done_time = 0

            if (self.spin_done_time > 30):
                new_state = State.DRY
            if (self.wiggle_count > 500 and self.wd_count < 100):
                new_state = State.DRY

        if (self.state != State.BOTH):
            self.spin_done_time = 0
                
        # regardless of current state, reset to null if we time out on low current
        if (self.null_count >= self.idle_time and self.state != 0):
            new_state = State.NONE

        if new_state != self.state:
            self.state = new_state
            return new_state
        
        return None

if __name__ == "__main__":
    p = HeuristicSignalProcessor()
    p.cal = 1.1
    lc = 0
    for line in sys.stdin:

        ns = p.process_sample(float(line))
        lc += 1
        if (ns is not None):
            print("%d: %d" % (lc,ns.value))