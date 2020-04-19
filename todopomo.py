"""
Reads in todo.txt file, generates list of To-Do objects, then runs these as
cycles of Pomodoros (25 or 50 minutes), before finally updating the
todo.txt file to take account of completed To-Dos and some metrics. A log is
also kept of all pomodoros and breaks for analysis.

list_of_todos: contains all To-Dos, whatever their state, from todo.txt
todays_list: subset of list_of_todos which can be run as Pomodoros, from where
             they are moved to done_list when completed
priority : typical is A, B, etc ; F: future - To-Dos you haven't started working
            on but want to be associated with a projects ;
            I: important ; U: urgent ; R: for routine stuff (daily or weekly)
todopomo_log.txt: sequential log of all Pomodoros and breaks

future improvements:
- display analysis and stats, ways of visualising progress
- make into flask app that can be run on NAS
- improve grouping by projects for feedback and visualisation
"""
import todotxtio as tdt
import pomodoro as pmd

import time
from datetime import datetime, timedelta
import os
import re

try:
    from PyQt5.QtWidgets import QMessageBox
    from PyQt5.Qt import QApplication
except ImportError:#
    has_qt = False
else:
    has_qt = True

#declare filenames used
TODO_TXT = 'todo.txt'            #the main todo.txt file, created elsewhere
#TODO_TXT = 'test_todo.txt'
TODO_TXT_TMP = 'todo_txt.tmp'#to save changes to To-Dos
LOG_FILE = 'todopomo_log.txt'    #to record pomodoros and breaks for analysis
#LOG_FILE = 'test_todopomo_log.txt'

def todo_id(todo_list):
    """
    Add IDs to To-dos that don't have one, functioning like a primary key.
    format: P_, today's date, underscore, incrementing number
    added to dictionary of todo.tags (key: tdid)
    """
    tagged_list = [todo for todo in todo_list if 'tdid' in todo.tags]
    to_tag_list = [todo for todo in todo_list if 'tdid' not in todo.tags]
    for i, todo in enumerate(to_tag_list):
        todo.tags['tdid'] = 'P_' + str(datetime.today().date().isoformat()) + "_" + str(i)
        tagged_list.append(todo)
    return tagged_list

def make_todays_list(list1, list2=[]):
    """
    Makes (or updates) a list of To-dos (typically todays_list) by removing
    (or, if a second list is provided, adding) To-do objects
    list1 : the list to be modified
    list2 : if given, the list from which items will be taken
    returns:  new/updated list
    """
    q_remove = "To remove any To-dos from this list, "
    q_add = "To add any To-dos to the main list, "
    q = 'please enter a comma-separated list of numbers.'
    #by default remove To_dos with priority F (ie future)
    list1 = [todo for todo in list1 if todo.priority != 'F']
    if list2:
        print("Current Todos are:")
        print_list(list1)
        q = q_add + q
        #only options are the difference of the two lists
        options = [todo for todo in list2 if todo not in list1]
    else:
        q = q_remove + q
        options = list1

    print(80*'#')
    print("List of options:")
    for i,o in enumerate(options):
        print("[{}] - {}".format(i,o))
    print(80*'#')

    while True:
        try:
            options_selected = set(input(q).split(",")) #avoid dupes
            if options_selected == {''}:
                break
            options_selected = list(map(int,options_selected)) #only ints list
            for i in options_selected:
                print("You selected:{}".format(options[i]))
            break
        except KeyboardInterrupt:
            print("KeyboardInterrupt - Returning to menu.")
            return list1
        except:
            print("Incorrect selection, please try again")
            continue
    if list2:
        new_list = list1 + [todo for i, todo in enumerate(list2)
                                             if i in options_selected]
    else:
        new_list = [todo for i, todo in enumerate(list1)
                                             if i not in options_selected]
    return new_list

def print_list(todo_list, options='RAF', completed='exclude'):
    """
    Print out enumerated list to give overview/aid selection
    options ; 's' for simple print out
    more complex: by To-do priority R (routine),A,B,C,..., F(future),
    P(project), I(important not urgent)
    """
    #ensure completed are not shown unless selected
    if completed == 'exclude':
         todo_list = tdt.search(todo_list,completed=False)
    print(80*'#')
    #print simple list
    if options == 's':
        for todo in todo_list:
            print(" * ",  todo)
    #print list by completion status, priority
    else:
        options = options.upper()
        #first separate into lists according to priority, store in dict
        dict_of_lists = {}
        list_of_keys = []
        codes = {'R' : 'Routine',
                'A' : 'Top priority',
                'I' : 'Important',
                'F' : 'Future',
                'P' : 'Project'
                                }
        if completed != 'exclude':
            completed_list = tdt.search(todo_list,completed=True)
            todo_list = tdt.search(todo_list,completed=False)
            dict_of_lists['Completed'] = completed_list
            list_of_keys.append('Completed')
        for o in list(options):
            if o in codes.keys():
                key = codes[o]
            else:
                key = 'Priority ' + o
            l = [todo for todo in todo_list if todo.priority == o]
            dict_of_lists[key]  = l
            todo_list = [todo for todo in todo_list
                              if todo not in set(l)]
            list_of_keys.append(key)
        dict_of_lists['Other priority'] = todo_list
        list_of_keys.append('Other priority')
        for key in list_of_keys:
            print(key,'To-dos :')
            for todo in dict_of_lists[key]:
                print(" * ",  todo)
            print(80*'+')
    print(80*'#')

def sort_todo_list(todo_list):
    '''
    Will sort a todo list (global variable, usually list_of_todos)
    by completion state (completed last), priority (routine, A,B, etc),
    and tdid (ie oldest first)

    Should be called after todo.txt is originally read in, or after later
    alterations such as changing todo priority.
    '''
    #by tdid -
    todo_list.sort(key=lambda x:x.tags['tdid'])
    #need to provide default since priority is optional
    todo_list.sort(key=lambda x: '0' if x.priority == 'R'
                                     else (x.priority if x.priority else ''))
    todo_list.sort(key=lambda x:x.completed)

def selection(todo_list, further_options='CRSF', default_option='0'):
    """
    Choose which To-do to run next - or one of the alternative options
    options_list should be a string e.g. "UFRS"
    returns either a 'todotxtio.Todo' object or a string (further_options)
    """

    #all possible non-To-do menu options - more can be added in future
    further_options_def = [("C", "Change or update the To-do list"),
                          ("F","Finish for the day - leave"),
                          ("R" , "Re-Start for the day"),
                          ("S" , "Show stats")
                          ]
    #convert argument into list of list of keys to be used on dict
    further_options_keys = list(further_options.upper())
    #generate selection options as list of tuples from To-do and further options
    options = [(str(i),o) for (i,o) in enumerate(todo_list)] \
            + [o for o in further_options_def if o[0] in further_options_keys]
    #also create corresponding dictionary for all options_list
    options_dict = {o[0]:o[1] for o in options}
    q1 = 'Please select a To-do from the list by typing a between 0 and {},'\
    ' or a letter for one of the further options!\n'.format(len(todo_list)-1)
    print(80*'#')
    print("Today's list of To-Dos is:")
    for o in options:
        print("[{}] - {}".format(o[0],o[1]))
    print(80*'#')

    while True:
        try:
            option_selected = input(q1).upper() or default_option
        except:
            #will exit after saving list
            print(" Exiting!")
            return 'F'
        if option_selected in options_dict.keys():
            print("You selected:{}".format(options_dict[option_selected]))
            break
        else:
            print("Incorrect selection, please try again")
    if option_selected in further_options_keys:
        return option_selected
    else:
        return options_dict[option_selected]

def write_pomo(start, stop, duration, tdid='break', todo_endpoint=''):
    """
    Log Pomodoros and breaks
    """
    start = start.isoformat(timespec='minutes')
    stop = stop.isoformat(timespec='minutes')
    line = "{0},{1},{2},{3},\"{4}\"\n".format(tdid, start, stop,
                                                    duration, todo_endpoint)
                           #escaped {4} so that commas don't mess up csv
    if not os.path.exists(LOG_FILE):
        fd = open(LOG_FILE, "w")
        fd.write("To-Do ID (tdid),start,end,duration,endpoint\n")
    else:
        fd = open(LOG_FILE, "a")
    fd.write(line)
    fd.close()

def pomo_settings(pomo_length,todo_endpoint):
    '''
    Set the length and endpoint of a Pomodoro
    '''
    q1 = "Do you want a single (25 minute) or double (50 minute) Pomodoro ?\n"\
    " Type S or D, or Enter for default({} min)".format(pomo_length)
    q2 = "Please specify the endpoint! (The default is \"{}\")\n After you hit"\
    " Enter, the Pomodoro will start!".format(todo_endpoint)
    while True:
        todo_sod = input(q1).upper() or pomo_length
        if todo_sod == "S":
            pomo_length = 25
            break
        elif todo_sod == "D":
            pomo_length = 50
            break
        elif todo_sod * 0 == 0: #to if check it's numeric ie the default value
            pomo_length = todo_sod
            break
        else:
            print("You typed the wrong key - please try again")
            continue
    todo_endpoint = input(q2) or todo_endpoint
    return pomo_length, todo_endpoint

def run_pomo(todo, rest=5):
    """
    Run one (or a cycle of) pomodoros based on a To-do, followed by break.
    Logs length of each completed pomodoro and break (todopomo_log.txt).
    To exit before completing (pomo or break), Ctrl+C breaks loop.
    Returns: completion state, number of pomos completed,
    time worked (pomo_cycle_duration in seconds)
    """
    #initialise counters and set pomo defaults
    pomo_count, pomo_cycle_duration = 0, 0
    pomo_length, todo_endpoint, completed = 50, "Not specified", "N"
    print(todo)
    while True:
        #pomo_length, todo_endpoint = pomo_settings(pomo_length,todo_endpoint)
        pomo_length, todo_endpoint = pomo_settings(0.1, todo_endpoint)
        pmd.display("Now working on :", todo)
        start = datetime.now()
        interrupted = tick(int(pomo_length) * 60)
        if interrupted:
            continue
        pmd.notify('pomodoro', 'Finished pomo, rest now.')
        stop = datetime.now()
        pomo_duration = (stop - start).seconds
        #cap duration at 20% extra
        if pomo_duration > 1.2 * pomo_length * 60:
            pomo_duration = 1.2 * pomo_length * 60
        pomo_count += pomo_length // 25 #50 minute pomos counts double
        pomo_cycle_duration += pomo_duration
        write_pomo(start, stop, pomo_duration, todo.tags['tdid'], todo_endpoint)
        q1 = "Run another Pomodoro for the same To-Do after the break? (Y/n)"
        q2 = "Back to the selection list after the break.\n"\
        "Is the To-do completed (type y), or just done for today (type N)?"
        another = input(q1) or "Y"
        if another.upper() == "N":
            completed = input(q2) or "N"
        pmd.display("Rest now")
        start = datetime.now()
        #interrupted = tick(rest * 60)
        interrupted = tick(2)
        stop = datetime.now()
        break_duration = (stop - start).seconds
        #cap break duration at 20% extra
        if break_duration > 1.2 * pomo_length * 60:
            break_duration = 1.2 * pomo_length * 60
        write_pomo(start, stop, break_duration)
        if interrupted:
            continue
        pmd.notify('pomodoro', 'Finished rest, work now.')
        if another.upper() == "N":
            pmd.display("Pomodoro cycle is complete, back to selection")
            break
    return completed.upper(), int(pomo_count), int(pomo_cycle_duration)

def feedback(pomo_done=0,time_today=0,done_list=[],todays_list=[]):
    '''
    Give feedback on completion of pomos and To-dos
    Remains to be implemented:
    add some info about previous days/weeks for comparison
    '''
    # metrics of stuff done today, compare to previous days/weeks
    print(80*'#')
    if pomo_done and time_today:
        print("So far you finished {} pomodoros and "\
        "you worked for {} seconds".format(pomo_done,time_today))
        print(80*'#')
    if done_list:
        print("You also completed {} To-dos.".format(len(done_list)))
        print("The To-dos completed are :")
        for i, todo in enumerate(done_list):
            print(i, " - ",  todo)
        print(80*'+')
    if todays_list:
        print("The remaining To-dos for today are :")
        for i, todo in enumerate(todays_list):
            print(i, " - ",  todo)
    print(80*'#' + '\n' + 80*'#')

def update_todo(todo,completed, pomo_count, pomo_cycle_duration):
    '''
    Updates a To-dos state: completion, pomodoro count (Pmd), total time (Ttotal)
    the latter as custom tags
    '''
    if completed == 'Y':
        #update completion status by adding a completion date, changes both
        todo.completion_date = datetime.today().date().isoformat()
    # create/update To-do tags: number of pomodoros, Total time as custom tags
    # NB - need to convert to str as tdt assumes that's data type
    if pomo_count and pomo_cycle_duration:
        todo.tags['Pmd'] = str(pomo_count + int(todo.tags.get('Pmd', 0)))
        todo.tags['Ttotal'] = str(pomo_cycle_duration + int(todo.tags.get('Ttotal', 0)))

def todo_list_menu_selection(list_of_todos, todays_list):
    '''
    Select various ways to update or edit the lists of To-Dos
    '''

    options = {"U" : "Update Today's To-do list",
               "R" : "Remove To-Dos from Today's list",
               "P" : "Change To-do priority",
               "A" : "Add new To-do",
               "E" : "Edit existing To-do",
               "M" : "Go back to main menu"
                  }

    q1 = "What would you like to change? Please select an option:"
    q2 = "Make your selection:"
    while True:
        print(80*'+' + '\n' + q1)
        for i,o in options.items():
            print("[{}] - {}".format(i,o))
        print(80*'+')
        try:
            option_selected = input(q2).upper() or "M"
        except:
            print("returning to main menu")
            option_selected = "M"
        if option_selected in options.keys():
            print("You selected:{}".format(options[option_selected]))
            #break
        else:
            print("Incorrect selection, please try again")
            continue
        if option_selected == "U":
            todays_list = make_todays_list(todays_list,list_of_todos)
        elif option_selected == "R":
            todays_list = make_todays_list(todays_list)
        elif option_selected == "P":
            list_of_todos = edit_todo(list_of_todos)
        elif option_selected == "A":
            list_of_todos,todays_list = add_new_todo(list_of_todos,todays_list)
        elif option_selected == "E":
            print('not implemented yet')
        elif option_selected == "M":
            break

    #sort modified lists
    sort_todo_list(list_of_todos)
    sort_todo_list(todays_list)
    #save modified list
    tdt.to_file(TODO_TXT_TMP,list_of_todos)
    print("Modified list saved!")
    return list_of_todos, todays_list

def add_new_todo(list_of_todos,todays_list):
    '''
    Creates a minimal To-Do (text, priority, projects), adds it to lists
    Returns updated list_of_todos, todays_list
    '''
    q1 = "Enter the description of the new To-do:"
    q2 = "Enter the priority:"
    #q3 = "Enter the project(s) as a comma-separated list:"
    q4 = "Should this be added to Today's list of To-Dos (Y/n) ?"
    #nested set comprehension equivalent to :
    #for todo in list_of_todos:
    #    for project in todo.projects:
    #         project
    projects = {project for todo in list_of_todos for project in todo.projects}
    q3 = "Enter xxxthe project(s) as a comma-separated list: \n"\
         "(Existing projects are: " + ", ".join(projects) + ")"
    t = input(q1)
    pt = input(q2).upper()
    pj = input(q3).replace(" ","").split(",")
    add_to_today = input(q4) or "Y"
    #instantiate To-Do
    todo = tdt.Todo(text=t,priority=pt, projects=pj)
    list_of_todos.append(todo)
    if add_to_today.upper() == "Y":
        todays_list.append(todo)
    #add tdid to new To-Do
    list_of_todos = todo_id(list_of_todos)
    return list_of_todos, todays_list

def edit_todo(list_of_todos):
    '''
    Change priority (or potentially other property) of existing todo
    '''
    priorities = 'ABCDEFIRU'
    q1 = "Enter the number corresponding to the To-Do you want to change:"
    q2 = "Enter the new priority (possible values:{})".format(list(priorities))
    #list all to-dos available for selection
    for i, option in enumerate(list_of_todos):
        print("[{}] - {}".format(i,option))
    #make todo selection
    while True:
        try:
            todo = list_of_todos[int(input(q1))]
            print("You selected:\n{}".format(todo))
            p = input(q2).upper()
            assert p in priorities
            break
        except KeyboardInterrupt:
            print("returning to menu")
            return list_of_todos
        except:
            print("Incorrect selection, please try again")
            continue
    todo.priority = p
    return list_of_todos

def tick(duration):
    try:
        pmd.cli_timer(duration)
    except KeyboardInterrupt:
        pmd.display("Interrupting")
        interrupt = True
    else:
        interrupt = False
    return interrupt


def main():
    #check if tmp file remains, if so, load it
    if os.path.isfile(TODO_TXT_TMP):
        list_of_todos = tdt.from_file(TODO_TXT_TMP)
        print('Loaded To-Dos from {} !'.format(TODO_TXT_TMP))
    else:
        #generate the main list of To-dos by reading in todo.txt
        list_of_todos = tdt.from_file(TODO_TXT)
    #save timestamped backup of todo.txt content
    backup_name = 'todo_txt_' + re.sub(r'\D+','',
                   datetime.now().isoformat(timespec='seconds'))
    #tdt.to_file(backup_name, list_of_todos)
    if os.path.isfile(TODO_TXT):
        os.rename(TODO_TXT,backup_name)
    #give IDs to all To-dos, sort list, save to todo_txt_tmp
    list_of_todos = todo_id(list_of_todos)
    sort_todo_list(list_of_todos)
    tdt.to_file(TODO_TXT_TMP,list_of_todos)
#    print_list(list_of_todos, completed='Y')
    #define today's list of To-Dos from those that aren't completed
    todays_list = make_todays_list(tdt.search(list_of_todos,completed=False))
    #initialise variables keeping track of Pomos done, their number, time spent
    done_list, pomo_done, time_today = [], 0, 0
    #loop for moving To-dos from today's list to done list by doing them
    while True:
        option_selected = selection(todays_list, "CRSF", default_option='0')
        if option_selected == 'C':
            list_of_todos, todays_list = todo_list_menu_selection(list_of_todos, todays_list)
            continue
        elif option_selected == 'F':
            print("That's it for today!")
            break
        elif option_selected == 'R':
            ###############NEED TO SAVE ANYTHING?????????????????????????????
            #re-initialise
            done_list, pomo_done, time_today = [], 0, 0
            #update todays_list by adding from todo.txt
            todays_list = make_todays_list(todays_list, list_of_todos)
            feedback(pomo_done,time_today,done_list,todays_list)
            continue
        elif option_selected == 'S':
            print("not yet implemented")
            continue
#        else: #has to be a To-do
        try:
            completed, pomo_count, pomo_cycle_duration = run_pomo(option_selected)
        except:
            print('\n',80*'$'+'\n '+40*'#~')
            print(25*' '+'Pomo run was interrupted !\n' + 40*'#~','\n',80*'$')
            continue
        #run pomodoro and keep track of metrics
        pomo_done += pomo_count
        time_today += pomo_cycle_duration
        #update the to-do that's going through a pomodoro cycle
        update_todo(option_selected, completed, pomo_count, pomo_cycle_duration)
        print('checking:', option_selected)
        #update the temprary todo.txt file
        tdt.to_file(TODO_TXT_TMP, list_of_todos)
        feedback(pomo_done,time_today,done_list,todays_list)
        if completed == "Y":
            print("You just finished:\n {} \n Well done!".format(option_selected))
            done_list.append(option_selected)
            todays_list.remove(option_selected)
        feedback(pomo_done,time_today,done_list,todays_list)
    #sort full list, overwrite the temporary todo.txt file
    sort_todo_list(list_of_todos)
    #save final list, overwriting the original
    tdt.to_file(TODO_TXT,list_of_todos)
    if os.path.isfile(TODO_TXT):
        print("saved current To-Dos to {}.".format(TODO_TXT))
    #remove tmp file - otherwise it will be loaded next time
    if os.path.isfile(TODO_TXT_TMP):
        os.remove(TODO_TXT_TMP)
        print("removed {}.".format(TODO_TXT_TMP))


if __name__ == "__main__":
    main()
