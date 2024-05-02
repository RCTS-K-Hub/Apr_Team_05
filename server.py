from flask import Flask, jsonify, request, send_file, abort
from flask_cors import CORS
from pymongo import MongoClient
import matplotlib.pyplot as plt
import matplotlib
from io import BytesIO
from threading import Lock
import logging
from bson.json_util import dumps
import numpy as np 

app = Flask(__name__)
CORS(app)
matplotlib.use('Agg')
plot_lock = Lock()
client = MongoClient('mongodb://localhost:27017/')
db = client['school_data']
collection = db['yearly_stats']

@app.route('/get_subjects_data', methods=['GET'])
def get_subjects_data():
    year = request.args.get('year')
    if not year:
        return jsonify({"error": "Year parameter is missing"}), 400

    # Fetch data for the specified academic year
    result = collection.find_one({"AcademicYear": year}, {"_id": 0, "SubjectsData": 1})
    if not result or 'SubjectsData' not in result:
        return jsonify({"error": "Data not found for the year"}), 404

    scores_output = {}
    for subject in result['SubjectsData']:
        for category, tests in subject['Test Scores'].items():
            # Fetch pretest and posttest scores
            pre_tests = [score for key, score in tests.items() if 'Pretest' in key]
            post_tests = [score for key, score in tests.items() if 'Posttest' in key]
            
            # Calculate averages of pre-tests and post-tests separately
            pre_average = np.mean(pre_tests) if pre_tests else 0
            post_average = np.mean(post_tests) if post_tests else 0
            
            # Calculate combined average of pre-tests and post-tests
            combined_average = np.mean(pre_tests + post_tests) if (pre_tests + post_tests) else 0
            
            # Organize data by subject and category
            scores_output[f'{subject["Subjects"]} - {category}'] = {
                'pretest': pre_tests,
                'posttest': post_tests,
                'pre_average': pre_average,
                'post_average': post_average,
                'combined_average': combined_average
            }

    return jsonify(scores_output)


@app.route('/data', methods=['GET'])
def get_data():
    year = request.args.get('year')
    if not year:
        return jsonify({"error": "Year parameter is missing"}), 400

    pipeline = [
        {"$match": {"AcademicYear": year}},
        {"$unwind": "$Data"},
        {"$group": {
            "_id": "$AcademicYear",
            "totalStudents": {"$sum": "$Data.Total Students"},
            "schoolsCovered": {"$sum": "$Data.Schools Covered"},
            "teachers": {"$sum": "$Data.Teachers"},
            "sponsors": {"$sum": "$Data.Sponsors"},
            "statesCovered": {"$sum": "$Data.States Covered"}
        }}
    ]

    results = list(collection.aggregate(pipeline))
    if not results:
        return jsonify({"error": "Data not found for the specified year"}), 404

    return jsonify(results[0])  # Send the aggregated data


@app.route('/student_data', methods=['GET'])
def get_student_data():
    year = request.args.get('year')
    if not year:
        return jsonify({"error": "Year parameter is missing"}), 400

    # Fetch data for the specified academic year
    result = collection.find_one({"AcademicYear": year}, {"_id": 0, "StudentData": 1})
    if not result or 'StudentData' not in result:
        return jsonify({"error": "Data not found for the year"}), 404

    student_data = result['StudentData']

    male_pre_marks = []
    male_post_marks = []
    female_pre_marks = []
    female_post_marks = []
    coed_pre_marks = []
    coed_post_marks = []

    for item in student_data:
        if item['Gender'] == 'Male':
            male_pre_marks.append(item['Pre Mid Marks'])
            male_post_marks.append(item['Post Mid Marks'])
        elif item['Gender'] == 'Female':
            female_pre_marks.append(item['Pre Mid Marks'])
            female_post_marks.append(item['Post Mid Marks'])
        if item['College'] == 'Co-ed College':
            coed_pre_marks.append(item['Pre Mid Marks'])
            coed_post_marks.append(item['Post Mid Marks'])

    return jsonify({
        "malePreMarks": male_pre_marks,
        "malePostMarks": male_post_marks,
        "femalePreMarks": female_pre_marks,
        "femalePostMarks": female_post_marks,
        "coedPreMarks": coed_pre_marks,
        "coedPostMarks": coed_post_marks
    })


@app.route('/plot/<int:index>', methods=['POST'])
def plot_data(index):
    year = request.json.get('year')
    if year not in ['2022-2023', '2023-2024']:
        return jsonify({'error': 'Invalid or unsupported academic year'}), 400

    data = list(collection.find({'AcademicYear': year}, {'_id': 0}))
    if not data:
        return jsonify({'error': 'No data available for the selected year'}), 404

    year_data = data[0]['Data']
    months = [item['Month'] for item in year_data]
    labels = ['Total Students','Schools Covered', 'Teachers', 'Sponsors', 'States Covered']
    colors = ['yellow','red', 'green', 'blue', 'purple']  # Expanded color list

    plt.figure(figsize=(10, 6))
    # Ensure only plotting up to available labels and colors
    label = labels[index % len(labels)]
    color = colors[index % len(colors)]
    values = [item[label] for item in year_data]
    plt.plot(months, values, marker='o', linestyle='-', color=color, label=label)

    plt.xlabel('Month')
    plt.ylabel('Count')
    plt.title(f'Trends for {year}')
    plt.legend()
    plt.grid(True)

    buf = BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)

    return send_file(buf, mimetype='image/png', as_attachment=True, attachment_filename=f"{year}_trends.png")


if __name__ == '__main__':
    app.run(debug=True)