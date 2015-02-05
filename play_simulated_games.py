#!/usr/bin/python
import os
import math
import time
import csv
import MySQLdb as mdb
import numpy as np 
import random
import sys

import matplotlib
matplotlib.use('Agg')

import test_model 
import cv2
import test_features_extraction as test_ft
from sklearn.externals import joblib
import gmm_training as model

import model_retraining_for_game as retrain
import object_learning_for_game as first
import extract_tags_per_game as extract


def RetrieveFeatureVector(feature_info,start,end):

    feature_vector=[]
   
    for index in xrange(start,end):  
	feature_vector.append(feature_info[index][1])
    return feature_vector


def build_model(cursor, tags, con):
    for i in range(2,17):
	retrain.Model_Retrain(i,con)
    
    np.set_printoptions(threshold='nan')
    
    #get all the different tags available
    cursor.execute("SELECT DISTINCT(tag) FROM TagInfoBk") 
    results=cursor.fetchall()
    
    tags = []
    for result in results:
	tags.append(result[0])
    
    count = 0
    
    #for each tag we select all the observation_ids that are related to it
    for tag in tags: 
	feature_matrix=[]#initialize feature matrix for each different tag
	cursor.execute("SELECT DISTINCT(observation_id) FROM TagInfoBk WHERE tag=%s",(tag))
	tag_obs_ids=cursor.fetchall()
	cursor.execute('SELECT id FROM Tags WHERE tag = %s', (tag))
	qid = cursor.fetchone()[0]

	should_train = False
	#for every observation/object of this spesific tag
	for obs_id in tag_obs_ids:
	    T = get_t(obs_id[0], qid, cursor)
	    if T > 3:
		should_train = True
		count = count + 1
		cursor.execute("SELECT COUNT(*) FROM FeatureInfo WHERE feature_id='0' AND observation_id='{0}'".format(obs_id[0]))
		num_of_images_per_oservation=cursor.fetchall()
		
		cursor.execute("SELECT feature_id,feature_value FROM FeatureInfo WHERE observation_id='{0}'".format(obs_id[0]))
		feature_info=cursor.fetchall()
		
		vv_seperator=len(feature_info)/num_of_images_per_oservation[0][0]
		
		new_fv=0 #flag to show when a feature vector given a capture starts (index in feature_info tuple)
		end_of_fv=vv_seperator#flag to show when a feature vector given a capture ends (index in feature_info tuple)
	 
		for capture_id in xrange(0,num_of_images_per_oservation[0][0]): 
		    feature_vector=RetrieveFeatureVector(feature_info,new_fv,end_of_fv) #create a feature vector given a capture 
		   
		    new_fv=new_fv+vv_seperator #update starting index of the vector
		    end_of_fv=end_of_fv+vv_seperator #update ending index of the vector
		    feature_matrix.append(feature_vector) #insert feature vectors into a matrix for each tag
	
	if should_train:
	    feature_matrix=np.asarray(feature_matrix)
	    model.ModelTraining(tag, feature_matrix, 777) #training the model
	    
    print count


def get_t(object_id, question_id, cursor):

    tag = get_tag(question_id, cursor)

    cursor.execute('SELECT COUNT(*) \
                    FROM descriptions \
                    WHERE description like %s \
                    AND oid = %s', ('%{0}%'.format(tag), object_id))

    return cursor.fetchone()[0]


def get_tval(cursor):
    cursor.execute('SELECT yes_answers/total_answers FROM Pqd')

    result = cursor.fetchall()

    tvals = []
    for r in result:
        tvals.append(float(r[0]))

    return tvals


def copy_into_answers(cursor, tags):
    cursor.execute("SELECT tag, answer, object from QuestionAnswers")
    results = cursor.fetchall()
    
    for result in results:
	cursor.execute("SELECT id from Tags where tag = %s", (result[0]))
	qid = cursor.fetchone()[0]
	cursor.execute("INSERT INTO answers (qid, oid, answer) VALUES (%s, %s, %s)", (qid, result[2], result[1]))
    
    
def get_questions_answers(object_id, cursor):
    cursor.execute('SELECT qid, oid, answer from answers where oid = %s', (object_id))

    results = cursor.fetchall()

    questions_answers = {}
    for i in range(1, 290):
        questions_answers[i] = []

    for qid, oid, answer in results:
        for i in range(1, 290):
            if int(qid) == i:
                questions_answers[i].append(int(answer))

    return questions_answers


def get_tag(question_id, cursor):
    cursor.execute('SELECT tag from Tags where id = %s', (question_id))

    return cursor.fetchone()[0]


def get_t(object_id, question_id, cursor):
    tag = get_tag(question_id, cursor)

    cursor.execute('SELECT COUNT(*) \
                    FROM Descriptions \
                    WHERE description like %s \
                    AND objectID = %s', ('%{0}%'.format(tag), object_id))

    return cursor.fetchone()[0]


def gen_init_prob(cursor):
    objects = {}

    for i in range(1, 18):
        objects[i] = get_questions_answers(i, cursor)

    return objects


def test_images(cursor):
    Pi = gen_image_probabilities(1, cursor)
    for i in range(0,17):
	for j in range(0,289):
	    print i, get_tag(j+1, cursor), Pi[i][j]
	print max(Pi[i]), min(Pi[i])


def score_tag_for_object(game_id, tag, object_id):
    image_path = folder + '/Game' + str(game_id) + '/obj' + str(object_id) + '.jpg'
    model = 'GMM_model_' + str(game_id)

    image = cv2.imread(image_path)
    feature_vector = test_ft.FeatureExtraction(image)

    return test_model.score_tag(feature_vector, model, tag)


def score_tag(feature_vector, model):
    prob = model.score([feature_vector])
    return math.e ** (prob[0] / 100000.0)


def get_model_info(cursor, game_id):
    feature_vectors = []
    for i in range(1,18):
	image_path = os.getcwd() + '/GAMES/Game' + str(game_id) + '/obj' + str(i) + '.jpg'
	image = cv2.imread(image_path)
	feature_vectors.append(test_ft.FeatureExtraction(image))
	
    models = {}
    model_folder = os.getcwd()+'/GMM_model_777'
    listing = os.listdir(model_folder)
    
    for model in listing:
	if model.endswith('.pkl'):
	    
	    model_clone = joblib.load(model_folder + '/' + model)
	    T = model.split('_', 1)[0]
	    T = T.lower()
	    cursor.execute("SELECT id FROM Tags WHERE tag = %s", (T))
	    qid = cursor.fetchone()[0]
	    models[qid] = model_clone
	    
    return models, feature_vectors


def gen_image_probabilities(game_id, cursor):
    models, feature_vectors = get_model_info(cursor, game_id)
    available_models = []
    probabilities = {}
    for i in range(0, 17):
	probability = []
	for j in range(1, 290):
	    if j in models:
		probability.append(score_tag(feature_vectors[i], models[j]))
		available_models.append(j-1)
	    else:
		pass
		probability.append(-1)
	probabilities[i] = probability
	print "Image " + str(i + 1) + " processed"
    
    for i in available_models:
	total = 0
	for j in range(0,17):
	    total = total + probabilities[j][i]
	for j in range(0,17):
	    probabilities[j][i] = probabilities[j][i] / total
   
    return probabilities


def get_best_question(objects, asked_questions, pO, start, cursor, game_id, Pi):
    tvals = get_tval(cursor)
    probabilities_yes = []
    probabilities_no = []

    top = (17 - start - 1)/2 + start + 1
    bottom = 17 - top
    bestDifference = 0
    bestD = 0

    for i in range(0, 17):
        probabilities_yes.append(0)
	probabilities_no.append(0)

    for i in range(1, 18):
        for j in range(1, 290):
            if j not in asked_questions:
                T = get_t(i, j, cursor)
                num_yes = sum(objects[i][j])
                length = len(objects[i][j])
	    		
		if Pi[i-1][j-1] == -1:
		    probabilities_yes[i-1] = pO[i-1] * (tvals[T] + (num_yes + 1.0)/(length + 2.0))
		    probabilities_no[i-1] = pO[i-1] * ((1 - tvals[T]) + (length - num_yes + 1.0)/(length + 2.0))
		else:
		    probabilities_yes[i-1] = pO[i-1] * (tvals[T] + (num_yes + 1.0)/(length + 2.0) + Pi[i-1][j-1])
		    probabilities_no[i-1] = pO[i-1] * ((1 - tvals[T]) + (length - num_yes + 1.0)/(length + 2.0) + 1 - Pi[i-1][j-1])
                probabilities_yes.sort()
                probabilities_yes.reverse()
		
		yes_indices = np.argsort(probabilities_yes)

                topProbYes = 0
                bottomProbYes = 0

		bottomProbNo = 0
		topProbNo = 0

                for x in range(start, top):
                    topProbYes = topProbYes + probabilities_yes[x]
		    topProbNo = topProbNo + probabilities_no[yes_indices[x]]

                for x in range(top, 17):
                    bottomProbYes = bottomProbYes + probabilities_yes[x]
		    bottomProbNo = bottomProbNo + probabilities_no[yes_indices[x]]

                topProbYes = topProbYes/(0.0 + top)
                bottomProbYes = bottomProbYes/(0.0 + bottom)
		
		topProbNo = topProbNo/(0.0 + top)
		bottomProbNo = bottomProbNo/(0.0 + bottom)

                if(abs(topProbYes - bottomProbYes) + abs(topProbNo - bottomProbNo) > bestDifference):
                    bestDifference = abs(topProbYes - bottomProbYes) + abs(topProbNo - bottomProbNo)
                    bestD = j

    return bestD


def get_subset_split(pO):	    
    bestDifference = 0
    
    pO_sorted = np.sort(pO)
    pO_args_sorted = np.argsort(pO)
    
    for x in range(0,17):
	print str(pO_args_sorted[x]) + " -> " + str(pO_sorted[x])

    diff = 0
    bestDiff = 0
    
    for x in range(0, pO_sorted.size-1):
	if pO_sorted[x+1] - pO_sorted[x] > diff:
	    diff = pO_sorted[x+1] - pO_sorted[x]
	    bestDiff = x

    return bestDiff


def ask_question(cursor, answer_data, OBJECT_WE_PLAY, bestD, answers, pO, tags, game_folder, objectlist, objects, Pi):
    probabilityD = get_tval(cursor)
    question_tag = tags[bestD]		
    #answer = raw_input("Is it " + tags[bestD] + "? (yes/no) ")
    #answer = answer.lower()
    answer = answer_data[OBJECT_WE_PLAY-1][bestD]
    print game_folder, OBJECT_WE_PLAY,objectlist[OBJECT_WE_PLAY-1][0],'qt->'+question_tag+' ' ,'ans->'+answer 

    if not (answer):
	    print game_folder, OBJECT_WE_PLAY,'qt->'+question_tag+' ' ,'sd'+answer+'<-', objectlist[OBJECT_WE_PLAY-1][0]
	    
	    sys.exit()
	    
    if answer == 'yes' or answer is 'yes':
	    answers.append(True)
	    if Pi[0][bestD-1] == -1:
		for objectID in range(0,17):
		    T = get_t(objectID+1, bestD, cursor)
		    N = sum(objects[objectID+1][bestD])
		    D = len(objects[objectID+1][bestD])
		    pO[objectID] = pO[objectID] * (probabilityD[T] + (N + 1)/(D + 2.0))		
	    else:
		for objectID in range(0,17):
		    print Pi[objectID][bestD-1]
		    T = get_t(objectID+1, bestD, cursor)
		    N = sum(objects[objectID+1][bestD])
		    D = len(objects[objectID+1][bestD])
		    pO[objectID] = pO[objectID] * ((probabilityD[T] + (N + 1)/(D + 2.0) + Pi[objectID][bestD-1]))

    else:
	    if answer =='no' or answer is 'no':
			answers.append(False)
			if Pi[0][bestD-1] == -1:
			    for objectID in range(0,17):
				T = get_t(objectID+1, bestD, cursor)
				N = sum(objects[objectID+1][bestD])
				D = len(objects[objectID+1][bestD])
				pO[objectID] = pO[objectID] * ((1 - probabilityD[T]) + (D - N + 1)/(D + 2.0))		    
			else:
			    for objectID in range(0,17):
				print Pi[objectID][bestD-1]
				T = get_t(objectID+1, bestD, cursor)
				N = sum(objects[objectID+1][bestD])
				D = len(objects[objectID+1][bestD])
				pO[objectID] = pO[objectID] * (((1 - probabilityD[T]) + (D - N + 1)/(D + 2.0) + 1 - Pi[objectID][bestD-1]))
				    
    pO = pO / np.sum(pO)
    
    with open("example.txt", "a") as myfile:
	    myfile.write(question_tag + " -> " + answer+ " \n")
	    myfile.write(str(pO) + "\n")
	
    return pO, answers


def train_initial_model(game_id):
    start_time = time.time()	

    if game_id == 1:
    	for x in xrange(1,18):
    		desc_index = 6 * (x - 1)
    		os.system(" /usr/lib/jvm/java-7-oracle/bin/java -Djava.library.path=/local2/awh0047/iSpy/jnaoqi-1.14.5-linux64/lib -Dfile.encoding=UTF-8 -classpath /local2/awh0047/iSpy/ISPY/iSpy/ispy/bin:/local2/awh0047/iSpy/simplenlg-v4.4.2.jar:/local2/awh0047/iSpy/jaws-bin.jar:/local2/awh0047/iSpy/lucene-analyzers-common-4.6.0.jar:/local2/awh0047/iSpy/lucene-core-4.6.0.jar:/local2/awh0047/iSpy/stanford-corenlp-full-2014-08-27/stanford-corenlp-3.4.1.jar:/local2/awh0047/iSpy/jnaoqi-1.14.5-linux64/lib/jnaoqi-1.14.5.jar:/local2/awh0047/iSpy/stanford-corenlp-full-2014-08-27/stanford-corenlp-3.4.1-models.jar:/local2/awh0047/iSpy/mysql-connector-java-5.1.30-bin.jar ObjectDescription " + str(x) + " \"" + objectlist[x-1][0] + "\" \"" + descriptions_for_retraining[desc_index] + "\"") 
    	first.Object_Learning(1, con)
    	print "Initial learning complete"
    	extract.Extract_Tags(1)
    
    elif game_id < 7:
    	for x in xrange(1,18):
    		desc_index = 6 * (x - 1) + game_id - 1
    		os.system(" /usr/lib/jvm/java-7-oracle/bin/java -Djava.library.path=/local2/awh0047/iSpy/jnaoqi-1.14.5-linux64/lib -Dfile.encoding=UTF-8 -classpath /local2/awh0047/iSpy/ISPY/iSpy/ispy/bin:/local2/awh0047/iSpy/simplenlg-v4.4.2.jar:/local2/awh0047/iSpy/jaws-bin.jar:/local2/awh0047/iSpy/lucene-analyzers-common-4.6.0.jar:/local2/awh0047/iSpy/lucene-core-4.6.0.jar:/local2/awh0047/iSpy/stanford-corenlp-full-2014-08-27/stanford-corenlp-3.4.1.jar:/local2/awh0047/iSpy/jnaoqi-1.14.5-linux64/lib/jnaoqi-1.14.5.jar:/local2/awh0047/iSpy/stanford-corenlp-full-2014-08-27/stanford-corenlp-3.4.1-models.jar:/local2/awh0047/iSpy/mysql-connector-java-5.1.30-bin.jar ObjectDescription " + str(x) + " \"" + objectlist[x-1][0] + "\" \"" + descriptions_for_retraining[desc_index] + "\"")	
    	retrain.Model_Retrain(game_id, con)
    	print "Learning for game " + str(game_id) + " complete"
    	extract.Extract_Tags(game_id)
    	
    else:
    	csv_answers = np.genfromtxt(folder+'/Answers/Game'+str(game_id-1)+'.csv',dtype=str, delimiter='\t')
    	for x in xrange(1,18):
    		tag_built_description = ""
    		for i in xrange(0, len(tags)):
    			if csv_answers[x-1][i] == 'yes' or csv_answers[x-1][i] is 'yes':
    				tag_built_description = tag_built_description + tags[i] + " "
    		os.system(" /usr/lib/jvm/java-7-oracle/bin/java -Djava.library.path=/local2/awh0047/iSpy/jnaoqi-1.14.5-linux64/lib -Dfile.encoding=UTF-8 -classpath /local2/awh0047/iSpy/ISPY/iSpy/ispy/bin:/local2/awh0047/iSpy/simplenlg-v4.4.2.jar:/local2/awh0047/iSpy/jaws-bin.jar:/local2/awh0047/iSpy/lucene-analyzers-common-4.6.0.jar:/local2/awh0047/iSpy/lucene-core-4.6.0.jar:/local2/awh0047/iSpy/stanford-corenlp-full-2014-08-27/stanford-corenlp-3.4.1.jar:/local2/awh0047/iSpy/jnaoqi-1.14.5-linux64/lib/jnaoqi-1.14.5.jar:/local2/awh0047/iSpy/stanford-corenlp-full-2014-08-27/stanford-corenlp-3.4.1-models.jar:/local2/awh0047/iSpy/mysql-connector-java-5.1.30-bin.jar ObjectDescription " + str(x) + " \"" + objectlist[x-1][0] + "\" \"" + tag_built_description + "\"")
    	retrain.Model_Retrain(game_id, con)
    	print "Learning for game " + str(game_id) + " complete"
    	extract.Extract_Tags(game_id)
	    
    training_time = time.time() - start_time
    
    return training_time


def clear_tag_data():
    cursor.execute("DELETE FROM TagInfo;")
    cursor.execute("ALTER TABLE TagInfo AUTO_INCREMENT = 1;")


def build_object_list(cursor):
    objectlist = []
    
    cursor.execute("SELECT DISTINCT(name) FROM NameInfo;")
    obj = cursor.fetchall()
    
    OBJ = np.asarray(obj)
    for OB in OBJ:
	    objectlist.append(OB)
	    
    return objectlist


def get_object_ids(cursor):
    obj_id = []

    cursor.execute("SELECT DISTINCT(observation_id) \
		   FROM NameInfo;")
    objid = cursor.fetchall()
    
    obj_ID = np.asarray(objid)
    for objID in obj_ID:
	    obj_id.append(objID[0])

    return obj_id


def get_tags(cursor):
    cursor.execute("SELECT tag \
		   FROM Tags")
    tags = cursor.fetchall()
    
    tags_list = []
    
    for tag in tags:
	tags_list.append(tag[0])
    
    return tags_list


def get_descriptions(oid, cursor):
    cursor.execute("SELECT description \
		   FROM Descriptions \
		   WHERE objectID = %s", (oid))
    descriptions = cursor.fetchall()
    
    return descriptions


def record_object_results(cursor, object_id, answers, questions, con, guess2say, result, gameID):
    
    for i in range(0, len(questions)):
	T = get_t(object_id, questions[i], cursor)
	
	if answers[i] == True:
	    cursor.execute("SELECT yes_answers FROM Pqd where t_value = %s", T)
	    yes_count = cursor.fetchone()[0]
	    cursor.execute("UPDATE Pqd SET yes_answers = %s WHERE t_value = %s", (yes_count + 1, T))
	    
	cursor.execute("SELECT total_answers FROM Pqd where t_value = %s", T)
	total_count = cursor.fetchone()[0]
	cursor.execute("UPDATE Pqd SET total_answers = %s WHERE t_value = %s", (total_count + 1, T))
	
	cursor.execute("INSERT INTO answers (oid, qid, answer) VALUES (%s, %s, %s)", (object_id, questions[i], answers[i]))
	    
	con.commit()

    if result == 0:
	result = 'lose'
    else:
	result = 'win'

    with open("game.txt", "a") as myfile:
	  myfile.write(str(gameID)+','+ str(object_id) +','+ str(guess2say)+"," + str(len(questions)) + "," + result  +  "\n")
    

def record_round_results(gameID, round_wins, round_losses):
    
    with open("game.txt", "a") as myfile:
	myfile.write("Round " + str(gameID) + ": ")	  
	myfile.write("Wins=" + str(round_wins) + ', Losses='+str(round_losses))
	myfile.write(" Accuracy: " + str(round_wins/float(17)) + "\n")


def guess_object(pO, object_guess, guess2say):

    print guess2say
    print object_guess
    if object_guess == guess2say:
	print 'won'
	return 1
    else:
	print 'lost'
	return 0


def play_object(cursor, object_id, tags, gameID, all_games, objectlist, con, Pi):
    objects = gen_init_prob(cursor)
    folder =  os.getcwd()    
    
    answer_data = np.genfromtxt(folder+'/Answers/Game'+str(gameID)+'.csv',dtype=str, delimiter='\t')
    NoOfQuestions = 0
    pO = []
    game_folder = all_games + '/Game' + str(gameID)
    
    print "+++++++++++++++" + game_folder + "+++++++++++++++"

    initial_prob = 1/float(17)  
    for item in xrange(0, 17):
	pO.append(initial_prob)			
    
    pO = np.asarray(pO)	
 
    objects = gen_init_prob(cursor)

    askedQuestions = []
    answers = []
    split = 0
    answer_data = np.genfromtxt('/local2/awh0047/iSpy/ISPY_PY/Answers/Game' + str(gameID) + '.csv',dtype=str, delimiter='\t')

    while np.sort(pO)[pO.size - 1] - np.sort(pO)[pO.size - 2] < 0.1:
	best_question = get_best_question(objects, askedQuestions, pO, split, cursor, gameID, Pi)
	askedQuestions.append(best_question)
        pO, answers = ask_question(cursor, answer_data, object_id, best_question, answers, pO, tags, game_folder, objectlist, objects, Pi)
	split = get_subset_split(pO)
    
    minimum=np.max(pO)
    itemindexes =[i for i,x in enumerate(pO) if x==minimum]
    A = np.asarray(object_list)
    guess = A[itemindexes]
    guess2say =  guess[0][0]
    
    result = guess_object(pO, objectlist[object_id-1][0], guess2say)

    record_object_results(cursor, object_id, answers, askedQuestions, con, guess2say, result, gameID)
    
    return result


def play_round(cursor, tags, gameID, all_games, objectlist, con):
    obj_ids = get_object_ids(cursor)
    
    Pi = gen_image_probabilities(gameID, cursor)
    
    NoOfQuestions = 0
    round_wins = 0
    round_losses = 0
    
    for OBJECT_WE_PLAY in obj_ids:
        result = play_object(cursor, OBJECT_WE_PLAY, tags, gameID, all_games, objectlist, con, Pi)
	if result == 0:
	    round_losses = round_losses + 1
	else:
	    round_wins = round_wins + 1
	    
    record_round_results(gameID, round_wins, round_losses)
    

def play_game(cursor, con):
    wins=0
    losses=0

    folder =  os.getcwd()
    all_games = folder + '/Human_Games'
    
    objectlist = build_object_list(cursor)
    tags = get_tags(cursor)

    for gameID in range(15,31):
	   play_round(cursor, tags, gameID, all_games, objectlist, con)
    
    with open("game.txt", "a") as myfile:
       myfile.write("Wins=" + str(wins) + ', Losses='+str(losses))


def main():
    con = mdb.connect('localhost', 'iSpy_team', 'password', 'iSpy_features')
    with con:
	cursor = con.cursor()

    #test_images(cursor)

    #build_model(cursor, get_tags(cursor), con)

    play_game(cursor, con)
    #copy_into_answers(cursor, get_tags(cursor))
    #con.commit()

  
		      
if __name__ == '__main__':
        sys.exit(main())
	