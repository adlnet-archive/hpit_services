## Overview

The HyperPersonalize Intelligent Tutor (HPIT) is an schemaless, event driven system
which specializes in the communication between distributed intelligent tutoring systems 
and specialized, machine learning algorithims, which we call plugins.

HPIT is a next generation system built on the backbone of open source web technologies.

At the most fundemental layer HPIT is a collection of RESTful webservices that assist in
the routing of messages between tutors and plugins. On top of this web services layer 
we have built a client side library in the Python programming language to assist in 
the creation of tutors and plugins and their communcation with HPIT.

HPIT is a publish and subscribe framework using event-driven methodologies. Tutors interact 
with the system by sending transactions which consist of a named event and a data payload. 
Plugins can listen to these events, perform an action, then submit a response back to HPIT,
which will ultimately be routed to the tutor that made the original request.

In addition, HPIT packages several baseline plugins which peform basic functions related
to intelligent tutoring systems.

## Getting started

HPIT requires Python 3.4. Make sure that you have this version of Python installed and
linked into your PATH. Most systems that come with Python have Python 2.7x branch installed.
You may need to install Python3.4 manually to get started depending on your operating system.

You can check your version of Python by typing: `python --version` or `python3 --version`

Once you have the right version of Python installed you should also have `virtualenv` 
and `pip` installed as well. If you are unfamiliar with either of these libraries I highly 
encourage you research them, as they will make working with HPIT much simpler.

Once you have pip and virtualenv installed you can install HPIT by:

1. Changing to the directory where you have downloaded hpit with: `cd /path/to/project`
2. Creating a new virtual environment with: `virtualenv my_environment`
3. Activating that environment with: `source my_environment/bin/activate`
4. Installing HPIT's dependencies with: `pip install -r requirements.txt`

Once you have the project dependencies setup you can begin working with HPIT via 
the HPIT manager. (See below)

To start the HPIT server type: `python3 manager.py start` and open your browser 
to http://127.0.0.1:8000.

## The HPIT Manager

The HPIT Manager can be used to quickly launch an HPIT server, configure plugins and tutors,
and monitor how data is being passed between entities within the HPIT system.

The HPIT manager can be run by typing: `python3 manager.py <command> <command_args>`

Depending on the command you wish to run the arguments to that command will vary. The command
line manager for HPIT will help you along the way. For example typing just `python3 manager.py`
will give you a list of commands that manager understands. Then typing 
`python3 manager.py your_command` will show you the arguments that that command can take and a
brief overview of what that command does.

Currently the HPIT Manager has the following commands:
- `python3 manager.py start` will start the HPIT server, all locally configured tutors, and all locally configured plugins.
- `python3 manager.py stop` will stop the HPIT server, all locally configured tutors, and all locally configured plugins.
- `python3 manager.py status` will show you whether or not the HPIT server is currently running.
- `python3 manager.py add plugin <name> <subtype>` will help you create plugins with the specified name and subtype.
- `python3 manager.py remove plugin <name>` will help you remove plugins with the specified name.
- `python3 manager.py add tutor <name> <subtype>` will help you create tutors with the specified name and subtype.
- `python3 manager.py remove tutor <name>` will help you remove tutors with the specified name.

## The tutor and plugin configuration

The goals behind the HPIT manager is to give TutorGen a way to create and destory large 
amount of entities for testing and evaluation of the software. Creating a new hpit 
entity (tutor/plugin) adds it to the 'configuration.json'. Removing an hpit entity 
removes it from the 'configuration.json' file. All entities within the configuration specify
4 things: 

    1. Whether it is a tutor or plugin (by virtue of being in the tutor or plugin list)
    2. active - Whether the plugin is currently running. (True if it is)
    3. name - The name of the entity. This is how the entity will register itself with HPIT.
    4. type - The subtype of the entity. e.g. 'example' or 'knowledge_tracer'

You normally will not need to edit this file by hand. It is recommended that you change the
configuration with the `python3 manager.py` add and remove commands instead.

## The HPIT Server in depth

The HPIT Server is nothing more than an event-driven publish and subscribe framework, built
specifically to assist plugins and tutors to communicate via RESTful webserver. It is 
schemaless, has no pre-defined events, and is agnostic to the kinds of data it routes 
between plugins and tutors. In additon HPIT provides fundemental support for sessions,
authentication, message routing, and entity tracking.

Anyone can wrap these RESTful webservices in a client side library and will be able to interact
with HPIT. We have delivered a client side library written in Python.

The server supports a variety of routes to handle the connection, polling, and transfer of 
data between HPIT entities.

---

### /plugin/disconnect
SUPPORTS: POST

Destroys the session for the plugin calling this route.

Returns: 200:OK

### /tutor/disconnect
SUPPORTS: POST

Destroys the session for the tutor calling this route.

Returns: 200:OK

### /transaction
SUPPORTS: POST
Submit a transaction to the HPIT server. Expect the data formatted as JSON
with the application/json mimetype given in the headers. Expects two fields in
the JSON data.
- name : string => The name of the event transaction to submit to the server
- payload : Object => A JSON Object of the DATA to store in the database

Returns 200:JSON -> 
- transaction_id - The ID of the transaction submitted to the database

### /responses
SUPPORTS: GET
Poll for responses queued to original sender of a transaction.

Returns: JSON encoded list of responses.

### /response
SUPPORTS: POST
Submits a response to an earlier transaction to the HPIT server. 
Expects the data formatted as JSON with the application/json mimetype 
given in the headers. Expects two fields in the JSON data.
- transaction_id : string => The transaction id to the transaction you're responding to.
- payload : Object => A JSON Object of the DATA to respond with

Returns: 200:JSON ->
- response_id - The ID of the response submitted to the database

### /
SUPPORTS: GET
Shows the status dashboard and API route links for HPIT.

### /plugin/\name\/unsubscribe/\event\
SUPPORTS: POST

Stop listening to an event type for a specific plugin with
the name .

Returns: 200:OK or 200:DOES_NOT_EXIST

### /plugin/\name\/subscribe/\event\
SUPPORTS: POST

Start listening to an event type for a specific plugin with
the name .

Returns: 200:OK or 200:EXISTS

### /plugin/connect/\name\
SUPPORTS: POST

Establishes a plugin session with HPIT.

Returns: 200:JSON with the following fields:
- entity_name : string -> Assigned entity name (not unique)
- entity_id : string -> Assigned entity id (unique)
Both assignments expire when you disconnect from HPIT.

### /plugin/\name\/subscriptions
SUPPORTS: GET
Lists the event names for transactions this plugin will listen to.
If you are using the library then this is done under the hood to make sure
when you perform a poll you are recieving the right transactions.

Returns the event_names as a JSON list.

### /plugin/\name\/transactions
SUPPORTS: GET
List the transactions queued for a specific plugin.

!!!DANGER!!!: Will mark the transactions as recieved by the plugin 
and they will not show again. If you wish to see a preview
of the transactions queued for a plugin use the /preview route instead.

Returns JSON for the transactions.

### /plugin/\name\/history
SUPPORTS: GET
Lists the transaction history for a specific plugin - including queued transactions.
Does not mark them as recieved. 

If you wish to preview queued transactions only use the '/preview' route instead.
If you wish to actually CONSUME the queue (mark as recieved) use the '/transactions' route instead.

DO NOT USE THIS ROUTE TO GET YOUR TRANSACTIONS -- ONLY TO VIEW THEIR HISTORY.

Returns JSON for the transactions.

### /plugin/\name\/preview
SUPPORTS: GET
Lists the transactions queued for a specific plugin. 
Does not mark them as recieved. Only shows transactions not marked as received.
If you wish to see the entire transaction history for 
the plugin use the '/history' route instead.

DO NOT USE THIS ROUTE TO GET YOUR TRANSACTIONS -- ONLY TO PREVIEW THEM.

Returns JSON for the transactions.

### /tutor/connect/\name\
SUPPORTS: POST

Establishes a tutor session with HPIT.

Returns: 200:JSON with the following fields:
- entity_name : string -> Assigned entity name (not unique)
- entity_id : string -> Assigned entity id (unique)
Both assignments expire when you disconnect from HPIT.

## Tutors in depth

A Tutor is an HPIT entity that can send transactions to HPIT. A transaction consists of
an event name and a payload. The event name is an arbitrary string that defines what is in
the payload. Plugins register to listen to transactions based on the event name. The 
transaction payload is an arbitrary JSON like document with data formatted based on plugin
requirements. The kinds of transactions a tutor can send is definied by the plugins 
currently registered with HPIT. The HPIT server itself does not define what these 
transactions look like, however HPIT does package some plugins as part of it's architecture.

For example the HPIT basic knowledge tracing plugin supports the following three events:
    - kt_set_initial - Sets the initial values for the knowledge tracer on the KT Skill.
    - kt_trace - Performs a knowledge tracing operation on the KT Skill.
    - kt_reset - Resets the inital values for the knowledge tracer on the KT Skill.

Depending on the event name(eg kt_set_initial, or kt_trace) the payload the plugin expects will be different.

Tutors may also listen to plugin responses, and respond to them. Plugins may or may not
send a response depending on the plugin.

## Plugins in depth

A Plugin is an HPIT entity that subscribes to (listens to) certain event names, recieves
transcation payloads, perfoms some arbitrary function based on the event and transaction
payload, and may or may not return a response to the original sender of the transaction.

A plugin may listen to and define any events it wishes. When a tutor sends a transcation
to HPIT, if a plugin has registered itself with HPIT, and if that plugin and subscribed
to the event name submitted with the tutor's transcation it will recieve a queued list
of transactions when it polls the HPIT server for data. It is expected that plugins will
do this type of polling periodically to see if any transactions have been queued for 
processing by HPIT.

When a plugin processes an event from HPIT, it will recieve all the information in the 
original transaction, including the information identifying the tutor that sent the
transaction. This identifying information is called the entity_id of the tutor.

A plugin may send a response to HPIT by providing the original transaction id, along with 
a response payload, which will be sent to the original sender of the transaction message.

It is possible for plugins to send transactions like tutors and respond to transactions
like tutors. In this way, it is possible for plugins to listen to, and refire event 
transactions while altering the event name of the transaction so that other dependent 
plugins can also respond to the original trasaction. This can create a daisy chaining
effect where plugins fire in series to process a complex series of messages.

## Tech Stack

HPIT exclusively uses Open Source Technologies. Currently our tech stack consists 
of the following:

- Python 3.4
- Flask
- Flask-PyMongo
- Jinja2
- PyMongo
- MongoDB
- Daemonize
- Requests
- Gunicorn

Information about specific versions can be found inside of requirements.txt

## License

HPIT is as of yet, unlicensed technology. It is a joint project between Carnegie Learning, 
TutorGen, Inc., and Advanced Distributed Learning. As of this original writing, the 
understood intention is to license this technology under a permissive Open Source License 
such as the BSD or MIT License. The final decision on how to license the technology has 
yet to be determined and this software should be thought of as proprietary in nature.