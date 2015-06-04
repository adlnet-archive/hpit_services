from hpitclient import Plugin

from pymongo import MongoClient

from bson import ObjectId
import bson

import time
import json

from hpit.management.settings_manager import SettingsManager
settings = SettingsManager.get_plugin_settings()

class KnowledgeTracingPlugin(Plugin):

    def __init__(self, entity_id, api_key, logger, args = None):
        super().__init__(entity_id, api_key)
        self.logger = logger
        self.mongo = MongoClient(settings.MONGODB_URI)
        self.db = self.mongo[settings.MONGO_DBNAME].hpit_knowledge_tracing
        self.db.ensure_index([
                ("sender_entity_id", 1),
                ("skill_id", 1),
                ("student_id",1)
            ])
        
        self.shared_messages = self.get_shared_messages(args)
        if not self.shared_messages:
            raise Exception("Failed to initilize; invalid shared_messages")
        
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
            "tutorgen.kt_set_initial":self.kt_set_initial_callback,
            "tutorgen.kt_reset":self.kt_reset,
            "tutorgen.kt_trace":self.kt_trace,
            "tutorgen.kt_batch_trace":self.kt_batch_trace,
            "tutorgen.kt_transaction":self.transaction_callback_method,
            "get_student_model_fragment":self.get_student_model_fragment})
        
        #self.register_transaction_callback(self.transaction_callback_method)
        
        #temporary POC code
        #response = self._get_data("message-owner/get_student_model_fragment")
        #if response["owner"] == self.entity_id:
        #    self._post_data("message-auth",{"message_name":"get_student_model_fragment","other_entity_id":"88bb246d-7347-4f57-8cbe-95944a4e0027"}) #problem manager
        #self._post_data("share-message",{"message_name":"get_student_model_fragment","other_entity_ids":["88bb246d-7347-4f57-8cbe-95944a4e0027"]}) #problem manager
        
        for k,v in self.shared_messages.items():
            self._post_data("share-message",{"message_name":k,"other_entity_ids":self.shared_messages[k]})
            
        
    def check_skill_manager(self, message):
        """
        This method is called to verify that the skill id is valid in a call to the knowledge tracer.
        """

        def _callback_sm(response):
            if not "error" in response: #response from skill manager
                existing = self.db.find_one({'student_id':str(message['student_id']),'skill_id':str(message['skill_id'])})
                if not existing:
                    self.db.insert({
                        'sender_entity_id': message['sender_entity_id'],
                        'skill_id': str(message['skill_id']),
                        'probability_known': message['probability_known'],
                        'probability_learned': message['probability_learned'],
                        'probability_guess': message['probability_guess'],
                        'probability_mistake': message['probability_mistake'],
                        'student_id': message['student_id'],
                    })
                else:
                    self.db.update(
                        {'student_id':str(message['student_id']),'skill_id':str(message['skill_id'])},
                         {'$set': {
                             'probability_known': message['probability_known'],
                             'probability_learned': message['probability_learned'],
                             'probability_guess': message['probability_guess'],
                             'probability_mistake': message['probability_mistake'],
                         }
                        }    
                    )
                    
                self.send_response(message["message_id"],{
                    'skill_id': str(message['skill_id']),
                    'probability_known': message['probability_known'],
                    'probability_learned': message['probability_learned'],
                    'probability_guess': message['probability_guess'],
                    'probability_mistake': message['probability_mistake'],
                    'student_id':message['student_id']
                })
            else:
                if self.logger:
                    self.send_log_entry("ERROR: getting skill, " + str(response))
                self.send_response(message["message_id"],{
                    "error":"skill_id " + str(message["skill_id"]) + " is invalid.",
                    "skill_manager_error": response["error"]
                })
        
        self.send("tutorgen.get_skill_name",{"skill_id":str(message["skill_id"])}, _callback_sm)
          
    def _default_values(self,sender_id,skill_id,student_id):
        if self.logger:
            self.send_log_entry("INFO: No initial settings for KT_TRACE message. Using defaults.")

        new_trace = {
            'sender_entity_id': sender_id,
            'skill_id': skill_id,
            'student_id': student_id,
            'probability_known': 0.75, #this would have been calculated below. But we just set it instead.
            'probability_learned': 0.33,
            'probability_guess': 0.33,
            'probability_mistake': 0.33,
        }

        return new_trace
        
    def _kt_trace(self,kt_config,correct):

        p_known = float(kt_config['probability_known'])
        p_learned = float(kt_config['probability_learned'])
        p_guess = float(kt_config['probability_guess'])
        p_mistake = float(kt_config['probability_mistake'])

        numer = 0
        denom = 1

        if correct:
            numer = p_known * (1 - p_mistake)
            denom = numer + (1 - p_known) * p_guess
        else:
            numer = p_known * p_mistake
            denom = numer + (1 - p_known) * (1 - p_guess)

        p_known_prime = numer / denom if denom != 0 else 0
        p_known = p_known_prime + (1 - p_known_prime) * p_learned

        return {
            'skill_id': kt_config['skill_id'],
            'student_id': kt_config['student_id'],
            'probability_known': p_known,
            'probability_learned': p_learned,
            'probability_guess': p_guess,
            'probability_mistake': p_mistake,
            }
        
    def kt_batch_trace(self,message):
        try:
            if self.logger:
                self.send_log_entry("RECV: kt_trace with message: " + str(message))
    
            try:
                sender_entity_id = message["sender_entity_id"]
                student_id = message["student_id"]
                skill_list = message["skill_list"]
            except KeyError:
                self.send_response(message['message_id'],{"error":"kt_batch_trace requires 'skill_list', and 'student_id'"})
                return
                
            if type(skill_list) is not dict:
                self.send_response(message["message_id"],{"error":"kt_batch_trace requires 'skill_list' to be dict"})
                return
            
            skills = list(skill_list.keys())
            
            kt_configs = self.db.find({"student_id":student_id,"sender_entity_id":sender_entity_id,"skill_id":{"$in":skills}})
            
            response_skills = {}
            for kt_config in kt_configs:
                trace = self._kt_trace(kt_config,skill_list[kt_config["skill_id"]])
                self.db.update({'_id': kt_config['_id']}, {'$set': {
                    'probability_known': trace["probability_known"]
                }})
            
                if self.logger:
                    self.send_log_entry("SUCCESS: kt_trace with new data: " + str(kt_config))
                    
                response = dict(trace)
                response_skills[kt_config["skill_id"]] = response
            
            insert_list = []
            for skill in skills:
                if skill not in response_skills:
                    trace = self._default_values(sender_entity_id,skill,student_id)
                    insert_list.append(trace)
                    
                    response_skills[skill] = dict(trace)
                    del response_skills[skill]["sender_entity_id"]
                    
            if insert_list:
                self.db.insert(insert_list,manipulate=False)
            
            self.send_response(message['message_id'],{"traced_skills":response_skills})
        
        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)      
            })
        
    
    #Knowledge Tracing Plugin
    def kt_trace(self, message):
        """
        This is the bulk of the knowledge tracing plugin. The knowledge tracer
        pairs the student_id, the skill_id of the knowledge being traced, and the tutor
        we are tracing together. In this method, if no initial settings were provided
        for this skill on this student with a kt_set_initial message we will initialize
        the initial settings with a 50% probability before running the trace. If that fails
        then we will return an error to the caller of this message.
        """
        
        try:
            if self.logger:
                self.send_log_entry("RECV: kt_trace with message: " + str(message))
    
            try:
                sender_entity_id = message["sender_entity_id"]
                skill_id = str(ObjectId(message["skill_id"]))
                student_id = message["student_id"]
                correct = message["correct"]
            except KeyError:
                self.send_response(message['message_id'],{"error":"kt_trace requires 'sender_entity_id', 'skill_id', 'student_id' and 'correct'"})
                return
            except bson.errors.InvalidId:
                self.send_response(message["message_id"],{"error":"kt_trace 'skill_id' is not a valid skill id"})
                return
            
            kt_config = self.db.find_one({
                'sender_entity_id':sender_entity_id,
                'skill_id': skill_id,
                'student_id':student_id
            })
            
            if not kt_config:
                response = self._default_values(sender_entity_id,skill_id,student_id)
                self.db.insert(dict(response))
                del response["sender_entity_id"]
            else:   
                trace = self._kt_trace(kt_config,correct)
                self.db.update({'_id': kt_config['_id']}, {'$set': {
                    'probability_known': trace["probability_known"]
                }})
                response = dict(trace)
        
            if self.logger:
                self.send_log_entry("SUCCESS: kt_trace with new data: " + str(kt_config))
            
            self.send_response(message['message_id'],response)
        
        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)      
            })

    def kt_set_initial_callback(self, message):
        try:
            if self.logger:
                self.send_log_entry("RECV: kt_set_initial with message: " + str(message))
            try:
                sender_entity_id = message["sender_entity_id"]
                skill = ObjectId(message["skill_id"])
                prob_known = message["probability_known"]
                prob_learned=  message["probability_learned"]
                prob_guess = message["probability_guess"]
                prob_mistake = message["probability_mistake"]
                student_id = message["student_id"]
            except KeyError:
                self.send_response(message['message_id'],{"error":"kt_set_initial requires 'sender_entity_id', 'skill_id', 'probability_known', 'probability_learned', 'probability_guess', 'probability_mistake', and 'student_id'"})
                return 
            except bson.errors.InvalidId:
                self.send_response(message["message_id"],{"error":"kt_trace 'skill_id' is not a valid skill id"})
                return
                
            kt_config = self.db.find_one({
                'sender_entity_id': message['sender_entity_id'],
                'skill_id': str(message['skill_id']),
                'student_id': str(message['student_id']),
            })
            
            if not kt_config:
                self.check_skill_manager(message)
            else:
                self.db.update({'_id': kt_config['_id']},
                    {'$set': {
                        'probability_known' : message['probability_known'],
                        'probability_learned' : message['probability_learned'],
                        'probability_guess' : message['probability_guess'],
                        'probability_mistake' : message['probability_mistake']
                    }})
    
                self.send_response(message['message_id'], {
                    'skill_id': str(message['skill_id']),
                    'probability_known': message['probability_known'],
                    'probability_learned': message['probability_learned'],
                    'probability_guess': message['probability_guess'],
                    'probability_mistake': message['probability_mistake'],
                    'student_id':str(message['student_id'])
                    })
        
        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)      
            })

    def kt_reset(self, message):
        try:
            if self.logger:    
                self.send_log_entry("RECV: kt_reset with message: " + str(message))
            
            try:
                sender_entity_id = message["sender_entity_id"]
                skill = ObjectId(message["skill_id"])
                student_id = message["student_id"]
            except KeyError:
                self.send_response(message['message_id'],{"error":"kt_reset requires 'sender_entity_id', 'skill_id', and 'student_id'"})
                return
            except bson.errors.InvalidId:
                self.send_response(message["message_id"],{"error":"kt_trace 'skill_id' is not a valid skill id"})
                return
               
            kt_config = self.db.find_one({
                'sender_entity_id': message['sender_entity_id'],
                'skill_id': str(message['skill_id']),
                'student_id': str(message['student_id'])
            })
    
            if kt_config:
                self.db.update({'_id': kt_config['_id']}, {'$set': {
                    'probability_known': 0.75,
                    'probability_learned': 0.33,
                    'probability_guess': 0.33,
                    'probability_mistake': 0.33
                }})
                self.send_response(message['message_id'], {
                    'skill_id': str(message['skill_id']),
                    'probability_known': 0.75,
                    'probability_learned': 0.33,
                    'probability_guess': 0.33,
                    'probability_mistake': 0.33,
                    'student_id':str(message["student_id"])
                })
            else:
                self.send_response(message["message_id"], {
                    "error": "No configuration found in knowledge tracer for skill/student combination."
                })
                
        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)      
            })


    def get_student_model_fragment(self,message):
        try:
            if self.logger:
                self.send_log_entry("GET STUDENT MODEL FRAGMENT" + str(message))
            try:
                student_id = message['student_id']
            except KeyError:
                self.send_response(message['message_id'],{
                    "error":"knowledge tracing get_student_model_fragment requires 'student_id'",
                })
                return
            
            skill_list = []
            skills = self.db.find({
                'student_id': str(message['student_id'])
            })
            
            for skill in skills:
                skill_list.append({
                    'skill_id': str(skill['skill_id']),
                    'probability_known': skill['probability_known'],
                    'probability_learned': skill['probability_learned'],
                    'probability_guess': skill['probability_guess'],
                    'probability_mistake': skill['probability_mistake'],
                    'student_id':str(skill['student_id'])
                })
            
            self.send_response(message['message_id'],{
                "name":"knowledge_tracing",
                "fragment":skill_list,
            })
            
        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)      
            })
    
    def transaction_callback_method(self,message):
        try:
            
            response_skills = {}
                
            if self.logger:
                self.send_log_entry("RECV: transaction with message: " + str(message))
                
            if message["sender_entity_id"] != self.transaction_manager_id:
                self.send_response(message["message_id"],{
                        "error" : "Access denied",
                        "responder" : "kt"
                })
                return 
    
            try:
                sender_entity_id = message["orig_sender_id"]
                student_id = message["student_id"]
                outcome = message["outcome"]
                skill_ids = dict(message["skill_ids"])
            except KeyError:
                self.send_response(message["message_id"],{"error": "knowledge tracing not done because 'skill_ids', 'student_id', or 'outcome' not found.","responder":"kt"})
                return
            except (TypeError,ValueError):
                self.send_response(message["message_id"],{"error": "knowledge tracing not done because supplied 'skill_ids' is not valid; must be dict.","responder":"kt"})
                return
            
            try:
                if outcome.lower() == "correct":
                    correct = True
                elif outcome.lower() == "incorrect":
                    correct = False
                else:
                    self.send_response(message["message_id"],{"error": "knowledge tracing not done because outcome was neither 'correct' or 'incorrect'","responder":"kt"})
                    return
            except:
                self.send_response(message["message_id"],{"error": "knowledge tracing not done because outcome was neither 'correct' or 'incorrect'","responder":"kt"})
                return
                
            
            
            skills = list(skill_ids.values())
            skill_ids_to_names = {y:x for x,y in skill_ids.items()}
            
            kt_configs = self.db.find({"student_id":student_id,"sender_entity_id":sender_entity_id,"skill_id":{"$in":skills}})
            
            response_skills = {}
            for kt_config in kt_configs:
                trace = self._kt_trace(kt_config,outcome)
                self.db.update({'_id': kt_config['_id']}, {'$set': {
                    'probability_known': trace["probability_known"]
                }})
            
                if self.logger:
                    self.send_log_entry("SUCCESS: kt_trace with new data: " + str(kt_config))
                    
                response = dict(trace)
                response_skills[skill_ids_to_names[kt_config["skill_id"]]] = response
            
            insert_list = []
            for skill in skills:
                if skill not in response_skills:
                    trace = self._default_values(sender_entity_id,skill,student_id)
                    insert_list.append(trace)
                    
                    response_skills[skill_ids_to_names[skill]] = dict(trace)
                    del response_skills[skill_ids_to_names[skill]]["sender_entity_id"]
                    
            if insert_list:
                self.db.insert(insert_list,manipulate=False)
    
            response ={}
            response["traced_skills"] = response_skills
            response["responder"] = "kt"
            self.send_response(message["message_id"],response)
            
        except Exception as e:
            self.send_response(message["message_id"],{
                "error":"Unexpected error; please consult the docs. " + str(e)      
            })
         
        
            
            
