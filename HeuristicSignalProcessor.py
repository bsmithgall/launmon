from SignalProcessor import State, SignalProcessor
from SpikeDetector import SpikeDetector
import sys
import math

# "Expert System" classifier for laundry status given current.
class HeuristicSignalProcessor(SignalProcessor):
    def __init__(self, 
        spike_max=200, wash_th=60, dry_th=700, 
        idle_time=16,both_idle_time=30,cal=1.0):

        self.spike_max = spike_max
        self.wash_spike_idle = 0
        self.wash_th = wash_th
        self.wash_time = 0
        self.dry_time = 0
        self.dry_th = dry_th
        self.null_count = 0
        self.idle_time = idle_time
        self.both_idle_time = both_idle_time
        self.both_idle_count = 0
        self.dry_min = 0
        self.cal = cal
        self.prev_sample = 0
        self.state = State.NONE
        self.spike_det = SpikeDetector(10,wash_th)
        self.count = -1

    def reset(self):
        self.__init__()
        self.spike_det.reset()

    def process_sample(self, sample, only_diff=True):
        spike = 0
        self.count += 1

        # use nan to represent a gap in data
        if math.isnan(sample):
            if (self.state == State.NONE):
                if only_diff:
                    return None
                return self.state
            else:
                self.reset()
                return State.NONE

        spike,spike_count = self.spike_det.process_sample(sample)

        self.wash_spike_idle +=1
        if (spike > 0 and spike < 300 and (self.dry_time == 0 or self.dry_time > 10)):
            # print("%d: washy spike! %dx%dx%d" % (self.count,spike,spike_count,self.wash_spike_idle))
            self.wash_spike_idle = 0

        diff = sample - self.prev_sample
        self.prev_sample = sample

        new_state = self.state

        # keep track of how long we've been under the wash threshold
        self.null_count = self.null_count + 1 if sample < self.wash_th else 0

        if (self.state == State.NONE): # NONE
            if (spike > self.dry_th):
                new_state = State.DRY
            elif (spike > self.wash_th):
                new_state = State.WASH
    
        elif (self.state == State.WASH): # WASH
            if (diff > self.dry_th or (spike > self.dry_th and spike_count <= 3)):
                new_state = State.BOTH
                self.dry_time = 0

        elif (self.state == State.DRY): # DRY
            self.dry_time += 1
            if sample < self.dry_th:
                new_state = State.NONE
            elif sample < self.dry_min:
                self.dry_min = sample
            elif spike > self.wash_th and spike < self.spike_max and self.dry_time > 10:
                new_state = State.BOTH
            
        elif (self.state == State.BOTH): # BOTH    
            self.dry_time += 1      
            # failsafe timeout -- if we don't see any wash-y spikes for 400 seconds, we're not washing
            if (self.wash_spike_idle > 400):
                print("WASH SPIKE TIMEOUT!")
                new_state = State.DRY      

            if (self.wash_time > 1200 and self.dry_time > 20):
                if (sample < (self.dry_min + self.wash_th)):
                    self.both_idle_count += 1
                    if (self.both_idle_count > self.both_idle_time):
                        new_state = State.DRY
                else:
                    self.both_idle_count = 0

            if (sample < self.dry_th):
                new_state = State.WASH
            elif (sample < self.dry_min):
                self.dry_min = sample
           
                
        # regardless of current state, reset to null if we time out on low current
        if (self.null_count >= self.idle_time and self.state != 0):
            new_state = State.NONE

        # cycle timer on washer
        if (self.state == State.WASH or self.state == State.BOTH):
            self.wash_time += 1
            pass

        if new_state != self.state:
            if (new_state == State.NONE):
                self.wash_time = 0
            if (new_state == State.DRY):
                self.wash_time = 0
                self.dry_time = 0
                self.dry_min = sample
            if (new_state == State.BOTH):
                self.both_idle_count = 0
                if (self.dry_min == 0):
                    self.dry_min = sample

            self.state = new_state
            return new_state
        
        if only_diff:
            return None
        return self.state

if __name__ == "__main__":
    p = HeuristicSignalProcessor()
    p.cal = 1
    lc = 0
    for line in sys.stdin:

        ns = p.process_sample(float(line))
        lc += 1
        if (ns is not None):
            print("%d: %d" % (lc,ns.value))