#! /usr/bin/env python
import probabilistic_rewards
import read_adversary
import prism_model
import numpy as np
import subprocess
import yaml
import sys
import os

def get_battery_model():
    ################ SPECIFY PATHS OF MODELS #######################
    path = '/home/milan/workspace/strands_ws/src/battery_scheduler'
    if os.path.isfile(path+'/models/battery_charge_model.yaml') and os.path.isfile(path+'/models/battery_discharge_model.yaml'):
        with open (path+'/models/battery_charge_model.yaml', 'r') as f_charge:
            charge_model = yaml.load(f_charge)
        with open (path+'/models/battery_discharge_model.yaml', 'r') as f_discharge:
            discharge_model = yaml.load(f_discharge)
        print ('Battery Models Found at: ' +path+'/models/battery_discharge_model.yaml'+', '+ path+'/models/battery_charge_model.yaml' )

        for model in [charge_model, discharge_model]:
            for b in model:
                bnext_dict = model[b]
                total = np.sum(np.array(bnext_dict.values()))
                for bn in bnext_dict:
                    bnext_dict[bn] = float(bnext_dict[bn])/total
        return charge_model, discharge_model
    else:
        raise ValueError('No models found. First create battery model with probabilistic_battery_model.py')
 

class FiniteHorizonControl:
    
    def __init__(self, init_battery, init_charging):
        ur = probabilistic_rewards.uncertain_rewards()
        self.task_prob, self.prob, self.clusters = ur.get_probabilistic_reward_model()
        self.charge_model, self.discharge_model = get_battery_model()
        self.cl_id = []
        self.sample_reward = []
        self.actual_reward = []
        self.exp_reward = []
        self.no_int = ur.no_int 
        self.no_days = len(ur.test_days)
        self.no_simulations = 1
        for z in range(self.no_int*self.no_days):
            self.exp_reward.append(sum(self.prob[z%self.no_int]*self.clusters))
   
        #######################SPECIFY LOCATION ######################
        self.main_path = '/home/milan/workspace/strands_ws/src/battery_scheduler'
        self.path_rew = self.main_path + '/data/sample_rewards'
        self.path_mod = self.main_path + '/models/'
        self.path_data = self.main_path + '/data/'
    
        if not os.path.isfile(self.path_rew):
            raise ValueError('Sample Rewards Not Generated. Generate rewards with generate_samples.py')

        with open(self.path_rew,'r') as f:
            for line in f:
                x = line.split(' ')
                self.cl_id.append(int(float(x[0].strip())))
                self.sample_reward.append(float(x[1].strip()))
                self.actual_reward.append(float(x[2].strip()))

        self.avg_totalreward = np.zeros((self.no_days))
        self.init_battery = init_battery
        self.init_charging = init_charging
        self.actions = []
        self.obtained_rewards = []
        self.battery = []
        self.charging = []
        self.time =[]
     
    def simulate(self):
        for k in range(self.no_days):
            self.pp = self.obtain_prism_model()
            battery = np.zeros((self.no_simulations))
            charging = np.zeros((self.no_simulations))
            init_cluster= np.zeros((self.no_simulations))
            tr_day = np.zeros((self.no_simulations))
            for i in range(self.no_simulations):
                final_state = self.simulate_day(k) 
                t, tp, o, e, b, ch, cl = self.pp.get_state(final_state) 
                battery[i] = int(b)
                print battery[i]
                charging[i] = int(ch)
                print charging[i]
                tr_day[i] = np.sum(self.obtained_rewards[k*self.no_int:(k+1)*self.no_int])
                
            self.init_battery = int(np.mean(battery))
            self.init_charging = int(np.mean(charging))
            self.avg_totalreward[k] = np.mean(tr_day)
            print self.init_battery, ' end battery'
            print self.init_charging, ' end charging'
    
        for k in range(len(self.avg_totalreward)):
            print self.avg_totalreward[k], ' total_reward, day',k+1
        print np.sum(self.avg_totalreward), ' : Reward for Aug'

    def simulate_day(self, day):
        current_state = self.pp.initial_state
        for i in range(self.no_int):
            print self.no_int*day+i, self.actual_reward[self.no_int*day+i]
            actions = []
            while not(('gather_reward' in actions) or ('go_charge' in actions) or ('stay_charging' in actions)):
                nx_s, trans_prob, actions = self.pp.get_possible_next_states(current_state)
                print nx_s, trans_prob, actions
                if all(a == 'observe' for a in actions):
                    for s in nx_s:
                        t, tp, o, e, b, ch, cl = self.pp.get_state(s)
                        if self.actual_reward[self.no_int*day+i] != 0 and tp == '1':
                            current_state = s
                        if self.actual_reward == 0 and tp == '0':
                            current_state = s 
                
                elif all(a == 'evaluate' for a in actions):
                    min_cl = np.inf
                    for s in nx_s:
                        t, tp, o, e, b, ch, cl = self.pp.get_state(s)
                        if abs(self.clusters[int(cl)] - self.actual_reward[self.no_int*day+i]) < min_cl:
                            current_state = s

                else:
                    ct, ctp, co, ce, cb, cch, ccl = self.pp.get_state(current_state)
                    self.charging.append(cch)
                    self.battery.append(cb)
                    self.time.append(self.no_int*day+int(ct))
        
                    if all(a == 'stay_charging' for a in actions):
                        prob = []
                        for s in nx_s:
                            t, tp, o, e, b, ch, cl = self.pp.get_state(s)                  
                            prob.append(self.charge_model[int(cb)][int(b)])
                        current_state = np.random.choice(nx_s, p=np.array(prob))
                        req_a = actions[nx_s.index(current_state)]
                        self.obtained_rewards.append(0)

                    elif all(a == 'go_charge' for a in actions):
                        prob = []
                        for s in nx_s:
                            t, tp, o, e, b, ch, cl = self.pp.get_state(s) 
                            if int(cb) == 100 or int(cb) == 99:                 
                                prob.append(self.charge_model[int(cb)][int(b)])
                            else:
                                prob.append(self.charge_model[int(cb)][int(b)+1])
                        current_state = np.random.choice(nx_s, p=np.array(prob))
                        req_a = actions[nx_s.index(current_state)]
                        self.obtained_rewards.append(0)
            
                    elif all(a == 'gather_reward' for a in actions):
                        prob = []
                        for s in nx_s:
                            t, tp, o, e, b, ch, cl = self.pp.get_state(s)                  
                            prob.append(self.discharge_model[int(cb)][int(b)])
                        current_state = np.random.choice(nx_s, p=np.array(prob))
                        req_a = actions[nx_s.index(current_state)]
                        self.obtained_rewards.append(self.actual_reward[self.no_int*day+i])

                    self.actions.append(req_a)
        
        return current_state


    def obtain_prism_model(self):
        pm = prism_model.PrismModel('model_t.prism', self.init_battery, self.init_charging, self.task_prob, self.clusters, self.prob, self.charge_model, self.discharge_model)
        #######################SPECIFY LOCATION ######################
        # running prism and saving output from prism
        with open(self.path_data+'result_fhc', 'w') as file:
            process = subprocess.Popen('./prism '+ self.path_mod + 'model_t.prism '+ self.path_mod +'model_prop.props -exportadv '+ self.path_mod+ 'model_t.adv -exportprodstates ' + self.path_mod +'model_t.sta -exporttarget '+self.path_mod+'model_t.lab',cwd='/home/milan/prism/prism/bin', shell=True, stdout=subprocess.PIPE)
            for c in iter(lambda: process.stdout.read(1), ''):
                sys.stdout.write(c)
                file.write(c)
        ##reading output from prism to find policy file
        policy_file = []
        with open(self.path_data+'result_fhc', 'r') as f:
            line_list = f.readlines()
            for i in range(len(line_list)):
                if 'Computed point: ' in line_list[i]:
                    el = line_list[i].split(' ')
                    req_point = el[2][1:-1]
                    if abs(1.0-float(req_point)) < 0.001:
                        start_p = len('Adversary written to file "'+self.path_mod)
                        file_name = line_list[i-1][start_p:-3]
                        policy_file.append((req_point, file_name))

                if 'Result:' in line_list[i]:
                    s_policy_file = sorted(policy_file, key= lambda x: abs(1-float(x[0])))
                    
                    if len(s_policy_file) == 1:
                        policy_file_name = s_policy_file[0][1]
                    elif '('+s_policy_file[0][0]+',' in line_list[i]:
                        policy_file_name = s_policy_file[0][1]
                    else:
                        policy_file_name = s_policy_file[1][1]

        #######################SPECIFY LOCATION AS BEFORE ######################
        print 'Reading from ', policy_file_name
        pp = read_adversary.ParseAdversary([policy_file_name, 'model_t.sta', 'model_t.lab'])
        return pp

    def get_plan(self, fname):
        print 'Writing plan..'
        with open(self.path_data + fname, 'w') as f:
            f.write('time battery charging  action  obtained_reward match_reward actual_reward exp_reward\n')
            for t, b, ch, a, obr, mr, ar, er in zip(self.time, self.battery, self.charging, self.actions, self.obtained_rewards, self.sample_reward, self.actual_reward, self.exp_reward):
                f.write('{0} {1} {2} {3} {4} {5} {6} {7}\n'.format(t, b, ch, a, obr, mr, ar, er))

if __name__ == '__main__':
    fhc = FiniteHorizonControl(70, 1)
    fhc.simulate()
    fhc.get_plan('fhc_aug')