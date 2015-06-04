from hpitclient import Plugin

from pymongo import MongoClient
from bson.objectid import ObjectId
import bson

from threading import Timer

from datetime import datetime

import time

from hpit.management.settings_manager import SettingsManager
settings = SettingsManager.get_plugin_settings()

import requests
import json

class StudentManagementPlugin(Plugin):

    def __init__(self, entity_id, api_key, logger, args = None):
        super().__init__(entity_id, api_key) 
        self.logger = logger
        self.mongo = MongoClient(settings.MONGODB_URI)
        self.db = self.mongo[settings.MONGO_DBNAME].hpit_students
        self.session_db = self.mongo[settings.MONGO_DBNAME].hpit_sessions
        
        self.TIMEOUT = 30
        self.student_model_fragment_names = ["knowledge_tracing","problem_management","hint_factory"]
        self.student_models = {}
        self.timeout_threads = {}
        
        if args:
            try:
                self.args = json.loads(args[1:-1])
                self.transaction_manager_id = self.args["transaction_management"]
            except KeyError:
                raise Exception("Failed to initialize; invalid transaction_management")
        else:
            raise Exception("Failed to initialize; invalid transaction_management")
        
        
    def post_connect(self):
        super().post_connect()
        
        self.subscribe({
            "tutorgen.add_student":self.add_student_callback,
            "tutorgen.get_student":self.get_student_callback,
            "tutorgen.set_attribute":self.set_attribute_callback,
            "tutorgen.get_attribute":self.get_attribute_callback,
            "tutorgen.get_student_model":self.get_student_model_callback,
            "tutorgen.student_transaction":self.transaction_callback_method,
            "tutorgen.get_students_by_attribute":self.get_students_by_attribute_callback,
            "tutorgen.get_or_create_student_by_attribute":self.get_or_create_student_by_attribute_callback
        })


    #Student Management Plugin
    def add_student_callback(self, message):
        try:
            if self.logger:
                self.send_log_entry("ADD_STUDENT")
                self.send_log_entry(message)
            
            try:
                attributes = message["attributes"]
            except KeyError:
                attributes = {}
            
            response = self._post_data("new-resource",{"owner_id":message["sender_entity_id"]}).json()
            resource_id = response["resource_id"]
                   
            student_id = self.db.insert({"attributes":attributes,"resource_id":str(resource_id),"owner_id":str(message["sender_entity_id"])})
            
            session_id = self.session_db.insert({"student_id":str(student_id),"date_created":datetime.now()})
            
            self.send_response(message["message_id"],{"student_id":str(student_id),"attributes":attributes,"resource_id":str(resource_id),"session_id":str(session_id)})
        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)      
            })
            
    def get_student_callback(self, message):
        try:
            if self.logger:
                self.send_log_entry("GET_STUDENT")
                self.send_log_entry(message)
            
            try:
                student_id = ObjectId(str(message["student_id"]))
            except:
                self.send_response(message["message_id"],{"error":"Must provide a valid 'student_id' to get a student"})
                return
            
            return_student = self.db.find_one({"_id":ObjectId(student_id)})
            if not return_student:
                self.send_response(message["message_id"],{"error":"Student with id " + str(student_id) + " not found."})
            else:
                session_id = self.session_db.insert({"student_id":str(student_id),"date_created":datetime.now()})
                self.send_response(message["message_id"],{"student_id":str(return_student["_id"]),"resource_id":str(return_student["resource_id"]),"attributes":return_student["attributes"],"session_id":str(session_id)})
        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)      
            })
            
    def set_attribute_callback(self, message):
        try:
            if self.logger:
                self.send_log_entry("SET_ATTRIBUTE")
                self.send_log_entry(message)
            
            try:
                student_id = ObjectId(str(message["student_id"]))
                attribute_name = str(message["attribute_name"])
                attribute_value = str(message["attribute_value"])
            except (KeyError, TypeError,ValueError):
                self.send_response(message["message_id"],{"error":"Must provide a 'student_id', 'attribute_name' and 'attribute_value'"})
                return
            except bson.errors.InvalidId:
                self.send_response(message["message_id"],{"error":"Must provide a valid 'student_id' for set_attribute"})
                return
            if not attribute_name or not attribute_value:
                self.send_response(message["message_id"],{"error":"Must provide a 'student_id', 'attribute_name' and 'attribute_value'"})
                return
            
            update = self.db.update({'_id':ObjectId(str(student_id))},{'$set':{'attributes.'+str(attribute_name): str(attribute_value)}},upsert=False, multi=False)
            if not update["updatedExisting"]:
                self.send_response(message["message_id"],{"error":"Student with id " + str(student_id) + " not found."})
            else:
                record = self.db.find_one({"_id":ObjectId(str(student_id))})
                self.send_response(message["message_id"],{"student_id":str(record["_id"]),"attributes":record["attributes"]})
        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)      
            })
            
    def get_attribute_callback(self, message):
        try:
            if self.logger:
                self.send_log_entry("GET_ATTRIBUTE")
                self.send_log_entry(message)
            
            try:
                student_id = ObjectId(str(message["student_id"]))
                attribute_name = str(message["attribute_name"])
            except (KeyError, TypeError, ValueError):
                self.send_response(message["message_id"],{"error":"Must provide a 'student_id' and 'attribute_name'"})
                return
            except bson.errors.InvalidId:
                self.send_response(message["message_id"],{"error":"Must provide a valid 'student_id' for get_attribute"})
                return
             
                
            student = self.db.find_one({'_id':ObjectId(str(student_id))})
            if not student:
                self.send_response(message["message_id"],{"error":"Student with id " + str(student_id) + " not found."})
                return
            else:
                try:
                    attr = student["attributes"][attribute_name]
                except KeyError:
                    attr = ""
                self.send_response(message["message_id"],{"student_id":str(student["_id"]),attribute_name:attr,"resource_id":student["resource_id"]})
        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)      
            })
            
    def get_students_by_attribute_callback(self,message):
        try:
            if self.logger:
                self.send_log_entry("GET_STUDENTS_BY_ATTRIBUTE")
                self.send_log_entry(message)
                
            try:
                attribute_name = str(message["attribute_name"])
                attribute_value = str(message["attribute_value"])
            except (KeyError, TypeError, ValueError):
                self.send_response(message["message_id"],{"error":"Must provide a 'attribute_name' and 'attribute_value'"})
                return
                
            return_students = []
            students = self.db.find({"attributes."+str(attribute_name):attribute_value})
            for student in students:
                session_id = self.session_db.insert({"student_id":str(student["_id"]),"date_created":datetime.now()})
                return_students.append({
                    "student_id":str(student["_id"]),
                    "resource_id":str(student["resource_id"]),
                    "attributes":student["attributes"],
                    "session_id":str(session_id)}
                 )
                
            self.send_response(message["message_id"],{"students":return_students})
            
        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)     
            })
    
    def get_or_create_student_by_attribute_callback(self,message):
        try:
            if self.logger:
                self.send_log_entry("GET_STUDENTS_BY_ATTRIBUTE")
                self.send_log_entry(message)
                
            try:
                attribute_name = str(message["attribute_name"])
                attribute_value = str(message["attribute_value"])
            except (KeyError, TypeError, ValueError):
                self.send_response(message["message_id"],{"error":"Must provide a 'attribute_name' and 'attribute_value'"})
                return
                
            student = self.db.find_one({"attributes."+str(attribute_name):attribute_value})
                  
            if not student:
                response = self._post_data("new-resource",{"owner_id":message["sender_entity_id"]}).json()
                resource_id = response["resource_id"]
                attributes = {attribute_name:attribute_value}   
                student_id = self.db.insert({"attributes":{attribute_name:attribute_value},"resource_id":str(resource_id),"owner_id":str(message["sender_entity_id"])})
            
                session_id = self.session_db.insert({"student_id":str(student_id),"date_created":datetime.now()})
                
            else:
                student_id = student["_id"]
                session_id = self.session_db.insert({"student_id":str(student_id),"date_created":datetime.now()})
                resource_id = student["resource_id"]
                attributes = student["attributes"]
                
            self.send_response(message["message_id"],{"student_id":str(student_id),"attributes":attributes,"resource_id":str(resource_id),"session_id":str(session_id)})
            

        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)     
            })  
    def get_student_model_callback(self,message):
        try:
            if self.logger:
                self.send_log_entry("GET_STUDENT_MODEL")
                self.send_log_entry(message)        
               
            if 'student_id' not in message:
                self.send_response(message["message_id"],{
                    "error":"get_student_model requires a 'student_id'",         
                })
                return
            student_id = message["student_id"]
            
            try:
                student = self.db.find_one({'_id':ObjectId(str(message["student_id"]))})
            except bson.errors.InvalidId:
                self.send_response(message["message_id"],{"error":"Must provide a valid 'student_id' for get_student_model"})
                return
                
            if not student:
                self.send_response(message["message_id"],{
                    "error":"student with id " + str(student_id) + " does not exist.",
                })
                return

            update = False
                  
            self.student_models[message["message_id"]] = {}
            self.timeout_threads[message["message_id"]] = Timer(self.TIMEOUT, self.kill_timeout, [message, student_id])
            self.timeout_threads[message["message_id"]].start()
    
            self.send("get_student_model_fragment",{
                    "update": update,
                    "student_id" : str(message["student_id"]),
            },self.get_populate_student_model_callback_function(student_id,message))
        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)      
            })

    def get_populate_student_model_callback_function(self, student_id, message):
        def populate_student_model(response):
            
            #check if values exist
            try:
                name = response["name"]
                fragment = response["fragment"]
            except KeyError:
                return
            
            #check if name is valid
            if response["name"] not in self.student_model_fragment_names:
                return

            #fill student model
            try:
                self.student_models[message["message_id"]][response["name"]] = response["fragment"]
                if self.logger:
                    self.send_log_entry("GOT FRAGMENT " + str(response["fragment"]) + str(message["message_id"]))
                    
            except KeyError:
                return
            
            #check to see if student model complete
            for name in self.student_model_fragment_names:
                try:
                    if self.student_models[message["message_id"]][name] == None:
                        break
                except KeyError:
                    break
            else:
                #student model complete, send response (unless timed out)
                student = self.db.find_one({'_id':ObjectId(str(message["student_id"]))})
                if message["message_id"] in self.timeout_threads:
                    self.send_response(message["message_id"], {
                        "student_id": str(student_id),
                        "student_model" : self.student_models[message["message_id"]],       
                        "cached":False,
                        "resource_id":student["resource_id"],
                        "message_id":str(message["message_id"]),
                    })
                   
                    try: 
                        
                        self.timeout_threads[message["message_id"]].cancel()
                        del self.timeout_threads[message["message_id"]]
                        del self.student_models[message["message_id"]]
                    except KeyError:
                        pass

                    return

        return populate_student_model
        
    def kill_timeout(self, message, student_id):
        if self.logger:
            self.send_log_entry("TIMEOUT " + str(message))
        
        student = self.db.find_one({'_id':ObjectId(str(message["student_id"]))})
        
        try:
            self.send_response(message["message_id"],{
                "error":"Get student model timed out. Here is a partial student model.",
                'student_id': student_id,
                "student_model":self.student_models[str(message["message_id"])],
                "resource_id":student["resource_id"],
                "message_id":str(message["message_id"])
            })
        except KeyError:
            self.send_response(message["message_id"],{
                "error":"Get student model timed out. Here is a partial student model.",
                'student_id': student_id,
                "student_model":{},
                "resource_id":student["resource_id"],
                "message_id":str(message["message_id"])
            })
        
        try:
            del self.timeout_threads[message["message_id"]]
            del self.student_models[message["message_id"]]
        except KeyError:
            pass
    
    def transaction_callback_method(self,message):
        try:
            
            if self.logger:
                self.send_log_entry("RECV: transaction with message: " + str(message))
            
            if message["sender_entity_id"] != self.transaction_manager_id:
                self.send_response(message["message_id"],{
                        "error" : "Access denied",
                        "responder": "student"
                })
                return 
            
            try:
                sender_entity_id = message["orig_sender_id"]
                student_id = message["student_id"]
                session_id = ObjectId(str(message["session_id"]))
            except KeyError:
                self.send_response(message['message_id'],{"error":"transaction for Student Manager requires a 'student_id' and 'session_id'","responder":"student"})
                return
            except bson.errors.InvalidId:
                self.send_response(message["message_id"],{
                        "error" : "The supplied 'session_id' is not a valid ObjectId.",
                        "responder":"student",
                        "success":False
                })
                return 
            
            existing_student_other_id = self.db.find_one({"attributes.other_id":str(message["student_id"])})
            if not existing_student_other_id:
                try:
                    existing_student = self.db.find_one({"_id":ObjectId(str(message["student_id"]))})
                    if not existing_student:
                        self.send_response(message['message_id'],{"error":"transaction failed; could not find student with id " + str(student_id) + ". Try using add_student first.","responder": "student"})
                        return
                    else:
                        return_id = existing_student["_id"]
                except bson.errors.InvalidId:
                    self.send_response(message['message_id'],{"error":"transaction failed; could not find student with id " + str(student_id) + ". Try using add_student first.","responder": "student"})
                    return
            else:
                return_id = existing_student_other_id["_id"]
            
            session = self.session_db.find_one({"_id":ObjectId(str(session_id)),"student_id":str(return_id)})
            if not session:
                self.send_response(message['message_id'],{"error":"transaction failed; could not find session with id " + str(session_id) +".  Try adding/getting a student for a valid session id.","responder": "student"})
                return
                
            self.send_response(message["message_id"],{
                "student_id":str(return_id),
                "session_id":str(session["_id"]),
                "responder":"student",
            })
        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)      
            })
        
