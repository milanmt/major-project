#! /usr/bin/env python

import probabilistic_tasks as probabilistic_rewards
# import discrete_task_model as probabilistic_rewards
# import probabilistic_rewards
from datetime import date
import bc_read_adversary
import bcth_prism_model
import generate_task_samples as generate_samples
# import generate_samples
import numpy as np
import subprocess
import roslib
import yaml
import sys
import os


def get_battery_model():
    path = roslib.packages.get_pkg_dir('battery_scheduler')
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
    
    def __init__(self, init_battery, init_charging, test_days, pareto_point):
        ur = probabilistic_rewards.uncertain_rewards(test_days)
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
        self.req_pareto_point = pareto_point
   
        self.main_path = roslib.packages.get_pkg_dir('battery_scheduler')
        self.path_rew = self.main_path + '/data/fhc_sample_rewards'
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
        self.pareto_point = []
     
    def simulate(self):
        for k in range(self.no_days):
            print 'Day: ', k 
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
            # print self.no_int*day+i, self.actual_reward[self.no_int*day+i]
            actions = []
            while not(('gather_reward' in actions) or ('go_charge' in actions) or ('stay_charging' in actions)):
                nx_s, trans_prob, actions = self.pp.get_possible_next_states(current_state)
                # print nx_s, trans_prob, actions
                if all(a == 'observe' for a in actions):
                    for s in nx_s:
                        t, tp, o, e, b, ch, cl = self.pp.get_state(s)
                        if self.actual_reward[self.no_int*day+i] != 0 and tp == '1':
                            current_state = s
                        if self.actual_reward[self.no_int*day+i] == 0 and tp == '0':
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
                        next_b = [] 
                        for s in nx_s:
                            t, tp, o, e, b, ch, cl = self.pp.get_state(s)                  
                            prob.append(self.charge_model[int(cb)][int(b)])
                            next_b.append(int(b))
                        current_state = np.random.choice(nx_s, p=np.array(prob))
                        
                        # current_battery = int(round(sum(np.array(next_b)*np.array(prob))))
                        # try:
                        #     current_state_ind = next_b.index(current_battery)
                        # except ValueError:
                        #     current_state_ind, closest_nb = min(enumerate(next_b), key=lambda x: abs(x[1]-current_battery))
                        # current_state = nx_s[current_state_ind]
                        
                        req_a = actions[nx_s.index(current_state)]
                        self.obtained_rewards.append(0)

                    elif all(a == 'go_charge' for a in actions):
                        prob = []
                        next_b = []
                        for s in nx_s:
                            t, tp, o, e, b, ch, cl = self.pp.get_state(s) 
                            next_b.append(int(b))
                            if int(cb) == 100 or int(cb) == 99:                 
                                prob.append(self.charge_model[int(cb)][int(b)])
                            else:
                                prob.append(self.charge_model[int(cb)][int(b)+1])
                        
                        current_state = np.random.choice(nx_s, p=np.array(prob))

                        # current_battery = int(round(sum(np.array(next_b)*np.array(prob))))
                        # try:
                        #     current_state_ind = next_b.index(current_battery)
                        # except ValueError:
                        #     current_state_ind, closest_nb = min(enumerate(next_b), key=lambda x: abs(x[1]-current_battery))
                        # current_state = nx_s[current_state_ind]

                        req_a = actions[nx_s.index(current_state)]
                        self.obtained_rewards.append(0)
            
                    elif all(a == 'gather_reward' for a in actions):
                        prob = []
                        next_b = []
                        for s in nx_s:
                            t, tp, o, e, b, ch, cl = self.pp.get_state(s)                  
                            prob.append(self.discharge_model[int(cb)][int(b)])
                            next_b.append(int(b))
                        
                        current_state = np.random.choice(nx_s, p=np.array(prob))

                        # current_battery = int(round(sum(np.array(next_b)*np.array(prob))))
                        # try:
                        #     current_state_ind = next_b.index(current_battery)
                        # except ValueError:
                        #     current_state_ind, closest_nb = min(enumerate(next_b), key=lambda x: abs(x[1]-current_battery))
                        # current_state = nx_s[current_state_ind]

                        req_a = actions[nx_s.index(current_state)]
                        self.obtained_rewards.append(self.actual_reward[self.no_int*day+i])

                    self.actions.append(req_a)
        
        return current_state


    def obtain_prism_model(self):
        pm = bcth_prism_model.PrismModel('model_t.prism', self.init_battery, self.init_charging, self.task_prob, self.clusters, self.prob, self.charge_model, self.discharge_model)
        
        #######################SPECIFY LOCATION ######################
        ### running prism and saving output from prism
        with open(self.path_data+'result_fhc', 'w') as file:
            process = subprocess.Popen('./prism '+ self.path_mod + 'model_t.prism '+ self.path_mod +'batterycost_model_prop.props -v -paretoepsilon 0.1 -exportadv '+ self.path_mod+ 'model_t.adv -exportprodstates ' + self.path_mod +'model_t.sta -exporttarget '+self.path_mod+'model_t.lab',cwd='/home/milan/prism/prism/bin', shell=True, stdout=subprocess.PIPE)
            for c in iter(lambda: process.stdout.read(1), ''):
                sys.stdout.write(c)
                file.write(c)
        
        ### reading output from prism to find policy file
        ### for dt
        policy_file = []
        pre1_point = None
        pre2_point = None
        with open(self.path_data+'result_fhc', 'r') as f:
            line_list = f.readlines()
            f_no_list = []
            pareto_points = []
            init = 0
            for e, line in enumerate(line_list):
                if 'pre1.adv' in line:
                    pre1_point = abs(float(line_list[e+1].split(',')[0].split('(')[1].strip()))

                if 'pre2.adv' in line:
                    pre2_point = abs(float(line_list[e+1].split(',')[0].split('(')[1].strip())) 

                if ': New point is (' in line:
                    el = line.split(' ')
                    if init == 0:
                        init_no = int(el[0][:-1])
                    cost40 = abs(float(el[4][1:-1]))
                    pareto_points.append(cost40)
                    f_no_list.append(str(int(el[0][:-1])-2))
                    init +=1 

        if 'pre1' == self.req_pareto_point or 'pre2' == self.req_pareto_point:
            f_no = self.req_pareto_point
            if self.req_pareto_point == 'pre1':
                self.pareto_point.extend(self.no_int*[pre1_point])
            elif self.req_pareto_point == 'pre2':
                self.pareto_point.extend(self.no_int*[pre2_point])

        else:
            if f_no_list:
                if self.req_pareto_point > 3:
                    approx_p_point = min(pareto_points) + ((max(pareto_points)-min(pareto_points))/3)*(float((self.req_pareto_point%3))/3)
                else:
                    approx_p_point = max(pareto_points)*(float(self.req_pareto_point)/3) ## 3 -> no. of pareto points being considered
                p_point = min(pareto_points, key=lambda x: abs(x-approx_p_point))
                self.pareto_point.extend(self.no_int*[p_point])
                f_ind = pareto_points.index(p_point)
                f_no = f_no_list[f_ind]
            else:
                f_no = None 
        
        if f_no != None:
            print 'Reading from model_t'+f_no+'.adv'
            pp = bc_read_adversary.ParseAdversary(['model_t'+f_no+'.adv', 'model_t.sta', 'model_t.lab'])
            return pp
        
        else:
            raise ValueError('Adversary Not Found!!!')

    
    def get_plan(self, fname):
        if 'pre1' == self.req_pareto_point or 'pre2' == self.req_pareto_point:
            plan_path = self.path_data + self.req_pareto_point + fname
        else:
            plan_path = self.path_data + 'p'+ str(self.req_pareto_point)+ fname
        print 'Writing plan to ', plan_path, ' ...'
        with open(plan_path, 'w') as f:
            f.write('time battery charging action obtained_reward match_reward actual_reward exp_reward pareto\n')
            for t, b, ch, a, obr, mr, ar, er, pp in zip(self.time, self.battery, self.charging, self.actions, self.obtained_rewards, self.sample_reward, self.actual_reward, self.exp_reward, self.pareto_point):
                f.write('{0} {1} {2} {3} {4} {5} {6} {7} {8}\n'.format(t, b, ch, a, obr, mr, ar, er, pp))


if __name__ == '__main__':
    # ############### Reward Days Set 1
    # sg = generate_samples.sample_generator(True, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)])

    # rewards = sg.rewards
    # cl_id = sg.cl_ids
    # act_rewards = sg.act_rewards
    # main_path = roslib.packages.get_pkg_dir('battery_scheduler')
    # path = main_path+'/data/fhc_sample_rewards'
    # with open(path,'w') as f:
    #     for r, c, a_r in zip(rewards, cl_id, act_rewards):
    #         f.write('{0} {1} {2} '.format(c, r, a_r))
    #         f.write('\n')

    np.random.seed(0)
    fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],1)## init_battery, init_charging, test_days, pareto point (0 - mincost)
    fhc.simulate()
    fhc.get_plan('fhc_ptest_1')

    # np.random.seed(0)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)], 0)## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_1')

    # # np.random.seed(1)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],0)## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_2')

    # np.random.seed(2)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],0)## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_3')

    # np.random.seed(0)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],1)## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_1')

    # np.random.seed(1)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],1)## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_2')

    # np.random.seed(2)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],1)## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_3')

    # np.random.seed(0)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],2)## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_1')

    # np.random.seed(1)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],2)## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_2')

    # np.random.seed(2)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],2)## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_3')

    # np.random.seed(0)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],3)## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_1')

    # np.random.seed(1)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],3)## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_2')

    # np.random.seed(2)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],3)## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_3')

    # np.random.seed(0)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],'pre1')## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_1')

    # np.random.seed(1)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],'pre1')## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_2')

    # np.random.seed(2)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],'pre1')## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_3')

    # np.random.seed(0)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],'pre2')## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_1')

    # np.random.seed(1)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],'pre2')## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_2')

    # np.random.seed(2)
    # fhc = FiniteHorizonControl(70, 1, [date(2017, 11, 10), date(2017, 10, 19),date(2017, 9, 28)],'pre2')## init_battery, init_charging, test_days, pareto point (0 - mincost)
    # fhc.simulate()
    # fhc.get_plan('fhc_dt_10111910289_3')

