# Battery Scheduler for Autonomous Mobile Robots

## Prerequisits
1. MongoDB, 'message_store' database with collection of 'task_events'.
2. PRISM - https://github.com/bfalacerda/prism
3. Clone of this repository with the files in the folder models. 

## Modifications
1. PRISM path should be modified. Look for ##SPECIFY LOCATION##
3. Select initialisation paramaters
  
## Running the files
1. Run roscore.
2. Run mongodb store
3. Run fhc.py for finite horizon control.
4. Run rhc.py for time based receding horizon control.
5. Run taskbased_rhc.py for event based receding horizon control.
5. Run taskbased_rbc*.py for rule based controls.
6. Run swtbrhc.py for sliding window based training for RHC controller

### General Script Description
While running these files, the following scripts are called:
1. generate_samples.py will generate test points. 
2. probabilistic_rewards.py generates the rewards and task model probabilities.
3. bcth_prism_model.py generates the prism script for model checking.
4. read_adversary.py reads the policies generated by prism.
5. In fhc.py and rhc.py simulation is done by obtaining the prism model, finding the next state and action taken from the current state from the optimal policy picked and accumalating these results across all the test points.
