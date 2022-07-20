import datetime
import json
import os


from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from ldap3.core.exceptions import LDAPAttributeOrValueExistsResult, LDAPAttributeError

from methods import read_csv, server_connection, add_csv_student, delete_student, modify_student_info, \
    search_student, search_student_in_cohort, enable_disable_student, isNaN, prepare_report, send_email, add_to_report

ldap_bp = Blueprint('ldap_blueprint', __name__)


@ldap_bp.route('/load_list', methods=['POST', 'GET'])
def uploader():
    if request.method == "POST":
        key = request.form['key']
        if key:
            return render_template('load_list.html', key=key)
        else:
            return render_template('service.html', key=key)
    else:
        return render_template('load_list.html')


@ldap_bp.route('/check_list/<key>', methods=['POST', 'GET'])
def check_list(key):
    data_path = "./data"
    isExist = os.path.exists(data_path)
    if not isExist:
        os.makedirs(data_path)
    if os.path.exists("./data/report.txt"):
        os.remove("./data/report.txt")

    with open("./data/report.txt", 'a') as file:
        file.write(f'\n{datetime.datetime.now().strftime("%d-%b-%Y (%H:%M:%S)")}')

    file.close()
    if request.method == "POST":
        # try:
            if key in ["Add", "Del", "Mod", "ACTV"]:
                f = request.files['fileupload']
                ldap_server = request.form['server-name']
                if not f:
                    message = "Please select a file"
                    if not ldap_server:
                        message = "Please select a file,Please enter server dn name"
                if not ldap_server:
                    message = "Please enter server dn name"
                if not f or not ldap_server:
                    flash(message)
                    return render_template('load_list.html', key=key)
                # check whether the specified path exists or not
                if os.path.exists("./data/list_student.csv"):
                    os.remove("./data/list_student.csv")
                # save csv file and server url in csv and txt file
                f.save(f"./data/{f.filename}")
                old_name = f"./data/{f.filename}"
                new_name = f"./data/list_student.csv"
                if os.path.exists(f"./data/list_student.csv"):
                    os.remove("./data/list_student.csv")
                os.rename(old_name, new_name)
                with open("./data/server_dn.txt", "w") as text_file:
                    text_file.write(ldap_server)
                text_file.close()
                if key == "Add":
                    return redirect(url_for('ldap_blueprint.add_students'))
                elif key == "Del":
                    return redirect(url_for('ldap_blueprint.delete_students'))
                elif key == "Mod":
                    return redirect(url_for('ldap_blueprint.modify_students'))
                elif key == "ACTV":
                    return redirect(url_for('ldap_blueprint.toggle_student_status'))
            elif key == "Inf":
                student_Id = request.form['student_Id']
                ldap_server = request.form['server-name']
                if not ldap_server:
                    message = "Please enter server dn name"
                    flash(message)
                    return render_template('load_list.html', key=key)

                if os.path.exists("./data/std_ID.txt"):
                    os.remove("./data/std_ID.txt")
                with open("./data/server_dn.txt", "w") as text_file:
                    text_file.write(ldap_server)
                text_file.close()
                    # print("The file has been deleted successfully")
                with open("./data/std_ID.txt", "w") as text_file:
                    text_file.write(student_Id)
                text_file.close()
                if not student_Id:
                    message = "Please enter student ID"
                    flash(message)
                    return render_template('load_list.html', key=key)
                else:
                    return redirect(url_for('ldap_blueprint.display_student_info'))

            elif key == "CRT":
                cohort_name = request.form['cohort_name']
                ldap_server = request.form['server-name']
                if not ldap_server:
                    message = "Please enter server dn name"
                    flash(message)
                    return render_template('load_list.html', key=key)
                if os.path.exists("./data/cohort.txt"):
                    os.remove("./data/cohort.txt")
                    # print("The file has been deleted successfully")
                with open("./data/server_dn.txt", "w") as text_file:
                    text_file.write(ldap_server)
                text_file.close()
                with open("./data/cohort.txt", "w") as text_file:
                    text_file.write(cohort_name)
                text_file.close()

                if not cohort_name:
                    message = "Please enter cohort name"
                    flash(message)
                    return render_template('load_list.html', key=key)
                else:
                    return redirect(url_for('ldap_blueprint.display_student_in_cohort'))
            else:
                flash("please select you action")
                return render_template('load_list.html')
        # except Exception as e:
        #     flash("please go home page and try again")
        #     return e

    if request.method == "GET":
        return render_template('load_list.html')


@ldap_bp.route('/toggle_status', methods=['POST', 'GET'])
def toggle_student_status():
    if request.method == "GET":
        return render_template('connect_ldap.html')
    elif request.method == "POST":
        ldap_user = request.form.get('uname')
        ldap_password = request.form.get('psw')
        with open("./data/server_dn.txt") as text_file:
            ldap_server = text_file.read()
            text_file.close()
        try:
            connect = server_connection(ldap_server, ldap_user, ldap_password)
            if connect:
                book = read_csv("./data/list_student.csv")
                enable_disable_student(book, connect)
                # email report
                receiver_email, message = prepare_report(connect)
                email_subject = 'Report'
                send_email(receiver_email, email_subject, message)
                connect.unbind()
                return render_template('service.html')
                # return redirect(url_for('main_blueprint.service'))
            else :
                alarm="There is a problem in connection to server (Credential Error)"
                return render_template('connect_ldap.html', alarm=alarm)
        except ValueError:
            alarm = "Error in setting,Please Define Environment Variables"
            return render_template('connect_ldap.html', alarm=alarm)


@ldap_bp.route('/adding_students', methods=['POST', 'GET'])
def add_students():
    if request.method == "GET":
        return render_template('connect_ldap.html')
    elif request.method == "POST":
        ldap_user = request.form.get('uname')
        ldap_password = request.form.get('psw')
        with open("./data/server_dn.txt") as text_file:
            ldap_server = text_file.read()
            text_file.close()
        if "\\" in ldap_user:
            try:
                connect = server_connection(ldap_server, ldap_user, ldap_password)
                if connect:
            # print("Successfully connect to the server")
                    book = read_csv("./data/list_student.csv")
                    add_csv_student(book, connect)
                    receiver_email, message=prepare_report(connect)
                    email_subject='Report'
                    send_email(receiver_email, email_subject, message)
                    connect.unbind()
                    return render_template('service.html')
                    # return redirect(url_for('main_blueprint.service'))
                else :
                    alarm = "There is a problem in connection to server (Credential Error)"
                    return render_template('connect_ldap.html', alarm=alarm)
            except ValueError:
                alarm = "Error in setting,Please Define Environment Variables"
                return render_template('connect_ldap.html', alarm=alarm)
        else:
            alarm = "Error in username.please modify the format of username"
            return render_template('connect_ldap.html', alarm=alarm)

@ldap_bp.route('/deleting_students', methods=['POST', 'GET'])
def delete_students():
    if request.method == "GET":
        return render_template('connect_ldap.html')
    elif request.method == "POST":
        ldap_user = request.form.get('uname')
        ldap_password = request.form.get('psw')
        with open("./data/server_dn.txt") as text_file:
            ldap_server = text_file.read()
            text_file.close()

        connect = server_connection(ldap_server, ldap_user, ldap_password)
        if connect:
            book = read_csv("./data/list_student.csv")
            delete_student(book, connect)
            receiver_email, message = prepare_report(connect)
            email_subject = 'Report'
            send_email(receiver_email, email_subject, message)
            connect.unbind()
            return render_template('service.html')
            # return redirect(url_for('main_blueprint.service'))
        else :
            alarm = "There is a problem in connection to server (Credential Error)"
            return render_template('connect_ldap.html', alarm=alarm)

@ldap_bp.route('/modify_students', methods=['POST', 'GET'])
def modify_students():
    if request.method == "GET":
        return render_template('connect_ldap.html')
    elif request.method == "POST":
        ldap_user = request.form.get('uname')
        ldap_password = request.form.get('psw')
        with open("./data/server_dn.txt") as text_file:
            ldap_server = text_file.read()
            text_file.close()
        connect = server_connection(ldap_server, ldap_user, ldap_password)
        if connect:
            book = read_csv("./data/list_student.csv")
            modify_student_info(book, connect)
            receiver_email, message = prepare_report(connect)
            email_subject = 'Report'
            send_email(receiver_email, email_subject, message)
            connect.unbind()
            return render_template('service.html')
            # return redirect(url_for('main_blueprint.service'))
        else:
            alarm = "There is a problem in connection to server (Credential Error)"
            return render_template('connect_ldap.html', alarm=alarm)


@ldap_bp.route('/search_Student', methods=['POST', 'GET'])
def display_student_info():
    if request.method == "GET":
        return render_template('connect_ldap.html')
    elif request.method == "POST":
        ldap_user = request.form.get('uname')
        ldap_password = request.form.get('psw')
        with open("./data/server_dn.txt") as text_file:
            ldap_server = text_file.read()
            text_file.close()
        connect = server_connection(ldap_server, ldap_user, ldap_password)
        if connect:
            with open("./data/std_ID.txt") as text_file:
                student_Id = text_file.read()
                st_list=['ST-','st-','sT-','St-']
                for item in st_list:
                    if item in student_Id:
                        student_Id=student_Id.replace(item,"")
                text_file.close()
            result = search_student(student_Id, connect)
                # return result
            receiver_email, message = prepare_report(connect)
            email_subject = 'Report'
            send_email(receiver_email, email_subject, message)
            connect.unbind()
            if type(result) is dict:
                return render_template('service.html', my_result=result)
            else :
                return render_template('service.html',text_message=result)
        else:
            alarm = "There is a problem in connection to server (Credential Error)"
            return render_template('connect_ldap.html', alarm=alarm)

@ldap_bp.route('/search_cohort', methods=['POST', 'GET'])
def display_student_in_cohort():
    if request.method == "GET":
        return render_template('connect_ldap.html')
    elif request.method == "POST":
        ldap_user = request.form.get('uname')
        ldap_password = request.form.get('psw')
        with open("./data/server_dn.txt") as text_file:
            ldap_server = text_file.read()
            text_file.close()
        connect = server_connection(ldap_server, ldap_user, ldap_password)
        if connect:
            with open("./data/cohort.txt") as text_file:
                cohort = text_file.read()
                text_file.close()
            result=search_student_in_cohort(cohort, connect)
            if type(result) is list:
                for item in range(len(result)):
                    flash(result[item])
                    add_to_report(result[item])
                receiver_email, message = prepare_report(connect)
                email_subject = 'Report'
                send_email(receiver_email, email_subject, message)
                connect.unbind()
                return render_template('service.html')
            else :
                add_to_report(result)
                receiver_email, message = prepare_report(connect)
                email_subject = 'Report'
                send_email(receiver_email, email_subject, message)
                connect.unbind()
                return render_template('service.html', text_message=result)

        else :
            alarm = "There is a problem in connection to server (Credential Error)"
            return render_template('connect_ldap.html', alarm=alarm)
