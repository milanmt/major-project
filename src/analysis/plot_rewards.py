#! /usr/bin/env python

import rospy
import pymongo
import read_tasks
import numpy as np
import pandas as pd 
import plotly
import plotly.plotly as py
import plotly.graph_objs as go
import matplotlib.pyplot as plt 
# import read_task_wo_priorities as read_tasks
from datetime import datetime, timedelta, time, date

class uncertain_rewards:
    def __init__(self, model_name):
        print 'Reading Tasks...'
        
        ## Old data
        tasks_processor = read_tasks.getTasks()
        self.tasks = tasks_processor.tasks_df

        ## Synthetic data
        # client = pymongo.MongoClient(rospy.get_param("mongodb_host", "localhost"),rospy.get_param("mongodb_port", 62345))
        # tasks = client.message_store.random_adder_tasks_nov2019.find(None)
        # start = []
        # end = []
        # priority = []
        # for task in tasks:
        #     start.append(datetime.utcfromtimestamp(task['start_after']['secs'])+timedelta(hours=5,minutes=30))
        #     end.append(datetime.utcfromtimestamp(task['end_before']['secs'])+timedelta(hours=5,minutes=30))
        #     priority.append(task['priority'])
        #     # priority.append(1)
        # self.tasks = pd.DataFrame(data = zip(start, end, priority), columns=['start_time', 'end_time', 'priority'])
        
        ## Common
        self.time_int = 30 #minutes
        self.no_int = 1440/self.time_int
        self.rewards_day  = dict()
        self.tasks['start_day'] = self.tasks['start_time'].apply(lambda x: x.date())
        self.tasks['end_day'] = self.tasks['end_time'].apply(lambda x: x.date())
                
   
    def __update_rewards_day(self, tasks, day): 
        max_end_day = tasks['end_day'].max()
        delta_days = (max_end_day - day).days
        for i in range (delta_days+1):
            rew_sum_day = np.zeros((self.no_int))
            start_int = datetime.combine(day,time(0,0))
            for i in range(self.no_int):
                end_int = start_int + timedelta(minutes=self.time_int)
                rew_sum_day[i] = self.tasks[(self.tasks['start_time'] < end_int) & (self.tasks['end_time'] > start_int)]['priority'].sum()
                start_int = end_int
            if day not in self.rewards_day:
                self.rewards_day.update({ day : rew_sum_day})
            else:
                self.rewards_day[day] += rew_sum_day
            day = day + timedelta(days=1)

    def get_organised_rewards(self):
        print 'Obtaining Rewards By Day...'
        days = self.tasks['start_day'].unique().tolist()
        for day in days:
            current_tasks = self.tasks[self.tasks['start_day']==day]
            self.__update_rewards_day(current_tasks, day)

        rew_matrix = np.array(self.rewards_day.values())
        expected_rewards = np.mean(rew_matrix, axis=0)

        return self.rewards_day, expected_rewards

if __name__ == '__main__':
    ur = uncertain_rewards(None)
    rewards_day, expected_rewards = ur.get_organised_rewards()
    # print(rewards_day)


    x0 = []
    y0 = []
    print(len(rewards_day))
    for day in rewards_day:
        # x0.extend(48*[day])
        # y0.extend(list(rewards_day[day]))
        print day
        x = [i for i in range(48)]
        plt.plot(x,rewards_day[day])
        plt.plot(x,expected_rewards,'r--')
        plt.show()
        

    # plt.scatter(x0,y0)
    # plt.show()


    # ur = uncertain_rewards('model1')
    # rewards_day = ur.get_organised_rewards()
    # print(rewards_day)

    # x1 = []
    # y1 = []
    # for day in rewards_day:
    # 	x1.extend(48*[day])
    # 	y1.extend(list(rewards_day[day]))


    # plt.scatter(x1,y1)
    # plt.show()

    # ur = uncertain_rewards('model2')
    # rewards_day = ur.get_organised_rewards()
    # print(rewards_day)

    # x2 = []
    # y2 = []
    # for day in rewards_day:
    #     x2.extend(48*[day])
    #     y2.extend(list(rewards_day[day]))


    # plt.scatter(x2,y2)
    # plt.show()

    # plotly.tools.set_credentials_file(username='MilanMariyaTomy', api_key= '8HntwF4rtsUwPvjW3Sl4')#username='ThanwiraSiraj', api_key= 'y9AlaR5JI6kYeCml1NG4') 
    # data = [go.Box( y=y1), go.Box(y=y2) ]

    # fig = go.Figure(data = data)
    # py.plot(fig, filename='reward_dist')
