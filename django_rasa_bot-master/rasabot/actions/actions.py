import logging
from msilib.schema import Error
from typing import Any, Text, Dict, List
import os
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import re
import string

from typing import Any, Text, Dict, List
import collections


import sqlite3
import random
from fuzzywuzzy import process
from api import loginApi

logging.basicConfig(level=logging.DEBUG)
db_file="./actions/app.db"

class AuthenticatedAction(Action):
    def name(self) -> Text:
        return "action_authenticated"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
            ) -> List[Dict[Text, Any]]:
            username = tracker.get_slot("username")
            password = tracker.get_slot("password")
            
            # Api call
            user_id = loginApi(username, password)
            
            if user_id is not None:
                dispatcher.utter_message(template="utter_authenticated_successfully")
                return [SlotSet("is_authenticated", True), SlotSet("student_id",user_id)]
            
            else:
                dispatcher.utter_message(template="utter_authentication_failure")
                    
            return []


class Queryspecialization(Action):

    def name(self) -> Text:
        return "query_specialization"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Runs a query using only the type column, fuzzy matching against the
        specialization slot. Outputs an utterance to the user w/ the relevent 
        information for one of the returned rows.
        """
        if tracker.slots.get("is_authenticated", False) == False:
            dispatcher.utter_message(template="utter_authentication_required")
            return []
        
        
        conn = DbQueryingMethods.create_connection(db_file=db_file)

        slot_value = tracker.get_slot("specialization")
        slot_name = "Faculty Name"
        
        # adding fuzzy matching, fingers crossed
        slot_value = DbQueryingMethods.get_closest_value(conn=conn,
            slot_name=slot_name,slot_value=slot_value)[0]

        get_query_results = DbQueryingMethods.select_by_slot(conn=conn,
            slot_name=slot_name,slot_value=slot_value)
        return_text = DbQueryingMethods.rows_info_as_text(get_query_results)
        dispatcher.utter_message(text=str(return_text))

        return []





class QueryDegree(Action):

    def name(self) -> Text:
        return "query_degree"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        """
        Runs a query using both the topic & type columns (fuzzy matching against the
        relevent slots). Finds a match for both if possible, otherwise a match for the
        type only, topic only in that order. Output is an utterance directly to the
        user with a randomly selected matching row.
        """
        if tracker.slots.get("is_authenticated", False) == False:
            dispatcher.utter_message(template="utter_authentication_required")
            return []

        conn = DbQueryingMethodsDegree.create_connection(db_file=db_file)

        # get matching entries for resource type
        course_name_value = tracker.get_slot("course")
        # make sure we don't pass None to our fuzzy matcher
        if course_name_value == None:
            course_name_value = " "
        course_name_name = "degree"
        course_name_value = DbQueryingMethodsDegree.get_closest_value(conn=conn,
            slot_name=course_name_name,slot_value=course_name_value)[0]
        query_results_type = DbQueryingMethodsDegree.select_by_slot(conn=conn,
            slot_name=course_name_value,slot_value=course_name_value)

        # # get matching for resource topic
        # resource_topic_value = tracker.get_slot("resource_topic")
        # # make sure we don't pass None to our fuzzy matcher
        # if resource_topic_value == None:
        #     resource_topic_value = " "
        # resource_topic_name = "Topic"
        # resource_topic_value = DbQueryingMethods.get_closest_value(conn=conn,    
        #     slot_name=resource_topic_name,slot_value=resource_topic_value)[0]
        # query_results_topic = DbQueryingMethods.select_by_slot(conn=conn,
        #     slot_name=resource_topic_name,slot_value=resource_topic_value)

        # intersection of two queries
      #  topic_set = collections.Counter(query_results_topic)
        topic_set = ""
        query_results_topic =""
        type_set =  collections.Counter(query_results_type)

        query_results_overlap = list((topic_set & type_set).elements())

        # apology for not having the right info
        apology = "I couldn't find exactly what you wanted, but you might like this."

        # return info for both, or topic match or type match or nothing
        if len(query_results_overlap)>0:
            return_text = DbQueryingMethodsDegree.rows_info_as_text(query_results_overlap)
        elif len(list(query_results_topic))>0:
            return_text = apology + DbQueryingMethodsDegree.rows_info_as_text(query_results_topic)
        elif len(list(query_results_type))>0:
            return_text = apology + DbQueryingMethodsDegree.rows_info_as_text(query_results_type)
        else:
            return_text = DbQueryingMethodsDegree.rows_info_as_text(query_results_overlap)
        
        # print results for user
        dispatcher.utter_message(text=str(return_text))

        return []

class DbQueryingMethods:
    def create_connection(db_file):
        """ 
        create a database connection to the SQLite database
        specified by the db_file
        :param db_file: database file
        :return: Connection object or None
        """
        conn = None
        try:
            conn = sqlite3.connect(db_file)
        except Error as e:
            print(e)

        return conn

    def get_closest_value(conn, slot_name, slot_value):
        """ Given a database column & text input, find the closest 
        match for the input in the column.
        """
        # get a list of all distinct values from our target column
        fuzzy_match_cur = conn.cursor()
        fuzzy_match_cur.execute(f"""SELECT DISTINCT {slot_name} 
                                FROM Faculty""")
        column_values = fuzzy_match_cur.fetchall()

        top_match = process.extractOne(slot_value, column_values)

        return(top_match[0])

    def select_by_slot(conn, slot_name, slot_value):
        """
        Query all rows in the tasks table
        :param conn: the Connection object
        :return:
        """
        cur = conn.cursor()
        cur.execute(f'''SELECT * FROM Faculty
                    WHERE {slot_name}="{slot_value}"''')

        # return an array
        rows = cur.fetchall()

        return(rows)

    def rows_info_as_text(rows):
        """
        Return one of the rows (randomly selcted) passed in 
        as a human-readable text. If there are no rows, returns
        text to that effect.
        """
        if len(list(rows)) < 1:
            return "There are no resources matching your query."
        else:
            for row in random.sample(rows, 1):
                return f"Try the {(row[4]).lower()} {row[0]} by {row[1]}. You can find it at {row[2]}."



class DbQueryingMethodsDegree:
    def create_connection(db_file):
        """ 
        create a database connection to the SQLite database
        specified by the db_file
        :param db_file: database file
        :return: Connection object or None
        """
        conn = None
        try:
            conn = sqlite3.connect(db_file)
        except Error as e:
            print(e)

        return conn

    def get_closest_value(conn, slot_name, slot_value):
        """ Given a database column & text input, find the closest 
        match for the input in the column.
        """
        # get a list of all distinct values from our target column
        fuzzy_match_cur = conn.cursor()
        fuzzy_match_cur.execute(f"""SELECT DISTINCT {slot_name} 
                                FROM StudentDegree INNER JOIN Student ON Student.id = StudentDegree.student
                                INNER JOIN Course ON Course.id = StudentDegree.course  """)
        column_values = fuzzy_match_cur.fetchall()

        top_match = process.extractOne(slot_value, column_values)

        return(top_match[0])

    def select_by_slot(conn, slot_name, slot_value):
        """
        Query all rows in the tasks table
        :param conn: the Connection object
        :return:
        """
        cur = conn.cursor()
        cur.execute(f'''SELECT DISTINCT {slot_name} 
                    FROM StudentDegree INNER JOIN Student ON Student.id = StudentDegree.student
                    INNER JOIN Course ON Course.id = StudentDegree.course 
                    WHERE {slot_name}="{slot_value}"''')

        # return an array
        rows = cur.fetchall()

        return(rows)

    def rows_info_as_text(rows):
        """
        Return one of the rows (randomly selcted) passed in 
        as a human-readable text. If there are no rows, returns
        text to that effect.
        """
        if len(list(rows)) < 1:
            return "There are no resources matching your query."
        else:
            for row in random.sample(rows, 1):
                return f"Try the {(row[4]).lower()} {row[0]} by {row[1]}. You can find it at {row[2]}."














class DbQueryingCourseMethods:
    def create_connection(db_file):
        """ 
        create a database connection to the SQLite database
        specified by the db_file
        :param db_file: database file
        :return: Connection object or None
        """
        conn = None
        try:
            conn = sqlite3.connect(db_file)
        except Error as e:
            print(e)

        return conn

    def get_closest_value(conn, slot_name, slot_value):
        """ Given a database column & text input, find the closest 
        match for the input in the column.
        """
        # get a list of all distinct values from our target column
        fuzzy_match_cur = conn.cursor()
        fuzzy_match_cur.execute(f"""SELECT university_class.claas_day, university_class.title, university_class.start_time,
                                university_class.end_time, university_course.title, 
                                CONCAT (user_user.first_name, user_user.last_name) 

                                FROM university_class  INNER JOIN university_branche ON university_branche.id = university_class.branche
                                INNER JOIN university_course ON university_course.id = university_class.course_id
                                INNER JOIN user_lecturer ON user_lecturer.id = university_class.lecturer_id
                                INNER JOIN user_user ON user_user.id = user_lecturer.lecturer_id""")
        column_values = fuzzy_match_cur.fetchall()

        top_match = process.extractOne(slot_value, column_values)

        return(top_match[0])
    
    def rows_info_as_text(rows):
        """
        Return one of the rows (randomly selcted) passed in 
        as a human-readable text. If there are no rows, returns
        text to that effect.
        """
        if len(list(rows)) < 1:
            return "There are no resources matching your query."
        else:
            for row in random.sample(rows, 1):
                return f"Try the {(row[4]).lower()} {row[0]} by {row[1]}. You can find it at {row[2]}."

"""
    def select_by_slot(conn, slot_name, slot_value):
        '''
        Query all rows in the tasks table
        :param conn: the Connection object
        :return:
        '''
        cur = conn.cursor()
        cur.execute(f'''SELECT * FROM Faculty
                    WHERE {slot_name}="{slot_value}"''')

        # return an array
        rows = cur.fetchall()

        return(rows)
"""


class QueryCourseInfo(Action):

    def name(self) -> Text:
        return "query_course_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        """
        Runs a query using both the topic & type columns (fuzzy matching against the
        relevent slots). Finds a match for both if possible, otherwise a match for the
        type only, topic only in that order. Output is an utterance directly to the
        user with a randomly selected matching row.
        """
        if tracker.slots.get("is_authenticated", False) == False:
            dispatcher.utter_message(template="utter_authentication_required")
            return []

        conn = DbQueryingCourseMethods.create_connection(db_file=db_file)

        # get matching entries for resource type
        course_name_value = tracker.get_slot("course_name")
        # make sure we don't pass None to our fuzzy matcher
        if course_name_value == None:
            course_name_value = " "
        course_name_name = "course"
        course_name_value = DbQueryingCourseMethods.get_closest_value(conn=conn,
            slot_name=course_name_name,slot_value=course_name_value)[0]
        query_results_type = DbQueryingCourseMethods.select_by_slot(conn=conn,
            slot_name=course_name_value,slot_value=course_name_value)

        topic_set = ""
        query_results_topic =""
        type_set =  collections.Counter(query_results_type)

        query_results_overlap = list((topic_set & type_set).elements())

        # apology for not having the right info
        apology = "I couldn't find exactly what you wanted, but you might like this."

        # return info for both, or topic match or type match or nothing
        if len(query_results_overlap)>0:
            return_text = DbQueryingCourseMethods.rows_info_as_text(query_results_overlap)
        elif len(list(query_results_topic))>0:
            return_text = apology + DbQueryingCourseMethods.rows_info_as_text(query_results_topic)
        elif len(list(query_results_type))>0:
            return_text = apology + DbQueryingCourseMethods.rows_info_as_text(query_results_type)
        else:
            return_text = DbQueryingCourseMethods.rows_info_as_text(query_results_overlap)
        
        # print results for user
        dispatcher.utter_message(text=str(return_text))

        return []