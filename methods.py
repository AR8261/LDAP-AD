import os
import secrets
import string
import smtplib
from email.message import EmailMessage
import pandas as pd
from flask import flash
from ldap3 import Server, Connection, ALL, NTLM, MODIFY_REPLACE, SUBTREE, ALL_ATTRIBUTES
from ldap3.core.exceptions import LDAPBindError


domain = os.environ.get('Domain')
domain_address = os.environ.get('domain_address')



email_smtp = os.environ.get('smtp')
college_email_address = os.environ.get('cea')
college_email_password = os.environ.get('cep')

def read_csv(path):
    """This function gives a path of a csv file and convert it  to a dictionary"""
    data = pd.read_csv(path)
    data_frame = pd.DataFrame(data)
    newData_frame = data_frame.transpose()  # will exchange columns with rows
    book = newData_frame.to_dict()
    return book

def add_csv_student(book, connect_ldap):
    """This function gives a list of student in the format of dictionary , and also should have a connection bind to
    the server  (with the help of ldap3 python library ),for every Item of dictionary ,It gives the student_Id and
    will search in the Active directory,if the student is existed ,it will flash a message that the student is
    existed, otherwise it will give all the attributes from the dictionary and store them in a dict called attr. Then
    based on the cohort name ,it will search if the organization unit of cohort is existed or not. If it is existed
    all attributes  will store to the related OU otherwise it will create the related organization unit ,based on the
    cohort's name. and do the same thing for groups.it will create groups and add the students to the related group.
    Finally, it creates a random password for each student and enable student and email the student to
    inform him/her about the password
        1- find if student is existed or not
            if it exists,it will quit
        2- check if the ou is existed or not
            if exists,
                it will add student to the suitable ou
                it will check if the group is exists or not
                if exist
                    it add the student to the group
                if not
                    it will create the group
                    add the student to the group
            if not exist
                creates th ou
                creattes group
                add student to the group and ou
        3- create a random password
        4- active student
        5 - send email to the student

     """
    counter=0
    for key in book.values():
        student_Id = key.get("StudentID")
        cohort = key.get("Cohort")
        # check if the student is in AD
        result = connect_ldap.search(domain, f'(sAMAccountName=St-{student_Id})',
                                         attributes={'objectclass', 'sn', 'cn', 'givenname', 'sAMAccountName'})
        if not result:
            receiver_email_address = key.get("Email")
            student_name = key.get("Firstname")
            student_family = key.get("Lastname")
            program = key.get("Program")
            ou_l=key.get("OU")
            if (isNaN(receiver_email_address) or isNaN(student_name) or isNaN(ou_l) or isNaN(student_family) or isNaN(program)):
                raise TypeError("Error in csv file")
            else:
                attr = {'givenName': student_name, 'sn': student_family, 'sAMAccountName': f"St-{student_Id}",
                    'mail': receiver_email_address, 'telephoneNumber': str(key.get("Phone")), 'cohortname': cohort,
                    'department': program, 'studentType': key.get("StudentType"),

                    'displayName': f'{student_name} {student_family}',
                    'userPrincipalName': f'St-{student_Id}@{domain_address}'}
                birthdate= key.get("DateOfBirth")
                lst = ["/", "-"]
                for item in lst:
                    if item in birthdate:
                        birthdate = birthdate.replace(item, '.')
                attr['birthdate']= birthdate
                name=f"{student_name} {student_family}"
                # check if the cohort is not exist ==>create it
                temp_list = [cohort[i:i + 2] for i in range(0, len(cohort), 2)]
                if (temp_list[1] == 'SW') or (temp_list[1] == "RW"):
                    semester = "W"
                elif (temp_list[1] == "SF") or (temp_list[1] == "RF"):
                    semester = "F"
                else:
                    semester = "S"
                ou_list = [f"Students-{semester}{temp_list[2]}", f"{ou_l}-{semester}{temp_list[2]}", f"{cohort}"]
                ou_location = f'ou={ou_list[2]},ou={ou_list[1]},ou={ou_list[0]}'
                create_ous(cohort, connect_ldap,ou_list)
                objectClass = ['user', 'person', 'organizationalPerson', 'top']
                user_dn = f'CN={name},{ou_location},{domain}'
                add_to_report(f"creating student {student_Id}")
                #add students to OU
                add_result = connect_ldap.add(user_dn, objectClass, attr)
                if add_result:
                    counter += 1
                    add_to_report(f"The {student_Id} added to the AD")
                    create_student_group(name, student_Id, connect_ldap,ou_list)
                # create password for user
                    new_password = password_generator()
                # new_student = Student(student_id=student_Id, password=new_password)
                # db.session.add(new_student)
                # db.session.commit()
                    success = connect_ldap.extend.microsoft.modify_password(user_dn, old_password=None,
                                                                            new_password=new_password)

                    if success:
                        add_to_report(f"password dedicated to {student_Id}")
                    else:
                        message=f"There is an error in dedication password to {student_Id} "
                        flash(message)
                        add_to_report(message)
                    attr = {'userAccountControl': [(MODIFY_REPLACE, [66048])]}
                    if connect_ldap.modify(user_dn, attr):
                        add_to_report(f"The {student_Id} added to the AD")
                        email_subject = "Welcome to MCIT"
                        message=prepare_email_students(message_route='templates/welcome_message.html', student_name=student_name, student_family=student_family, student_id=student_Id, password=new_password,
                                                   cohort=cohort, program=program)
                        send_email(receiver_email_address, email_subject, message)

                        create_student_group( name, student_Id, connect_ldap,ou_list)
                    else:
                        message=f"There is an error in activating {student_Id}"
                        add_to_report(message)
                        flash(message)
                else :
                    message=f"There is an error in adding {student_Id}"
                    flash(message)
                    add_to_report(message)
        else:
            message = f"The user {student_Id} is already exist!!"
            flash(message)
            add_to_report(message)
    message = f"{counter} number of students added successfuly"
    flash(message)

def server_connection(server_uri, admin_username, admin_password):
    """This function gives server uri ,admins username and password
    and try to connect to the ldap server"""
    try:
        server = Server(server_uri, connect_timeout=5, get_info=ALL)
        connection = Connection(server=server,
                                user=admin_username,
                                password=admin_password,
                                authentication=NTLM,
                                auto_bind=True)
        bind_response = connection.bind()
        if bind_response:
            return connection
        else:
            return connection.last_error
    except LDAPBindError:
        message='Unable to connect to the server'
        add_to_report(message)
        flash(message)
        return None

def create_ous(cohort, connect_ldap,ou_list):
    """This function gives a cohort's name and creates the related organization units and groups
    into the Active Directory"""

    mylist = []
    group_dict= {}
    for item in ou_list:
        group_name=item
        ou = f'OU={item}'
        search_filter = f'(&(objectClass=organizationalUnit)({ou}))'
        mylist.insert(0,ou) # it will add the ou in the first location of list
        ou_dn = f'{",".join(mylist)},{domain}'
        group_dn = f"cn={group_name},{ou_dn}"
        # print(group_dn)
        group_dict[group_name]=group_dn
        isExist = connect_ldap.search(search_base=ou_dn, search_filter=search_filter)
        if not isExist:
            isadded = connect_ldap.add(ou_dn, 'organizationalUnit')  # add ous
            if not isadded:
                message=f"The {ou_dn}did not add. "
                flash(message)
                add_to_report(message)
            else :
                message=f" {ou_dn} has been created ."
                add_to_report(message)
        else:
            add_to_report(f"the cohort {cohort}exists")
            continue

def create_student_group(name, student_id, connect_ldap,ou_list):
    """This function will create a group based on the cohort name and then
    add the student to the related group"""

    #create main group
    ou_dn=""
    group_name=""
    search_ou = f'(&(objectClass=organizationalUnit)(msDS-parentdistname=DC=mcit-test03,DC=local))'
    connect_ldap.search(search_base=domain, search_filter=search_ou, attributes={'name'})

    for entry in connect_ldap.response:
        group_name = entry['attributes']['name']
    search_filter = f'(&(objectClass=group)(msDS-parentdistname={domain}))'
    groupisExist = connect_ldap.search(search_base=domain, search_filter=search_filter,
                                       attributes={'objectclass', 'cn', 'name', 'sAMAccountName', 'groupType'})

    group_dict={}
    if not groupisExist:
        group_dn = f"cn={group_name},{domain}"
        attr = {}
        attr['sAMAccountName'] = group_name
        attr['name'] = group_name
        attr['groupType'] = 0x80000008
        objectClass = ['top', 'group']
        connect_ldap.add(group_dn, objectClass, attr)
        add_to_report(f" the group {group_name} is created in {domain}")
        group_dict[group_name] =group_dn
    else :
        group_dn = f"cn={group_name},{domain}"
        group_dict[group_name] = group_dn

    #create cohort groups

    mylist = []
    for item in ou_list:
        group_name = item
        ou = f'OU={item}'
        mylist.insert(0, ou)  # it will add the ou in the first location of list
        ou_dn = f'{",".join(mylist)},{domain}'
        group_dn_item = f"cn={group_name},{ou_dn}"
        group_dict[group_name] = group_dn_item

    for i in range(3, 0, -1):
        group_dn_base = list(group_dict.values())[i]
        group_name = list(group_dict.keys())[i]
        search_filter = f'(&(objectClass=group)(sAMAccountName={group_name}))'

        isExist = connect_ldap.search(search_base=group_dn_base, search_filter=search_filter,
                                      attributes={'objectclass', 'cn', 'name', 'sAMAccountName', 'groupType'})

        if not isExist:
            attr = {}
            attr['sAMAccountName'] = group_name
            attr['name'] = group_name
            attr['groupType'] = 0x80000008
            objectClass = ['top', 'group']
            connect_ldap.add(group_dn_base, objectClass, attr)
            add_to_report(f" the group {group_name} is created in {group_dn_base}")


    for i in range(3, 1, -1):
        n_group_dn_base = list(group_dict.values())[i]
        n_group_dn = list(group_dict.values())[i - 1]
        n_group_name = list(group_dict.keys())[i]
        search_filter = f'(&(&(objectClass=user)(sAMAccountName={n_group_name}))(memberOf={n_group_dn}))'
        search_scope = 'SUBTREE'
        attributes = ['memberOf']
        isExist = connect_ldap.search(search_base=n_group_dn, search_scope=search_scope,
                                          search_filter=search_filter,
                                          attributes=attributes)
        if not isExist:
            isadded = connect_ldap.extend.microsoft.add_members_to_groups(n_group_dn_base, n_group_dn)
            if (isadded):
                add_to_report(f"Adding group {n_group_name}to group.{n_group_dn}....")
            else:
                message=f"There is a problem in adding {n_group_name} to group {n_group_dn}"
                flash(message)
                add_to_report(message)

    student_group_dn=list(group_dict.values())[3]
    main_group_dn=list(group_dict.values())[0]
    add_student_to_existing_group(student_id, name, student_group_dn, ou_dn, connect_ldap,main_group_dn)

def add_student_to_existing_group(student_id, name, group_dn, search_base, connect_ldap,main_group_dn):

    """This function will add a user to the related existing group"""
    user_dn = f'cn={name},{search_base}'
    search_filter = f'(&(&(objectClass=user)(sAMAccountName=St-{student_id}))(memberOf={group_dn}))'
    search_scope = 'SUBTREE'
    attributes = ['cn', 'givenName', 'sn', 'telephoneNumber', 'mail', 'sAMAccountName', 'memberOf', 'member']
    isExist = connect_ldap.search(search_base=search_base, search_scope=search_scope, search_filter=search_filter,
                                  attributes=attributes)
    if not isExist:
        if connect_ldap.extend.microsoft.add_members_to_groups(user_dn, group_dn):
            add_to_report(f"Adding user {student_id} to group.{group_dn}....")
        else:
            message=f"There is a problem in adding student {student_id} to group {group_dn}"
            flash(message)
            add_to_report(message)
    else:
        add_to_report(f"The student {student_id} is already a member of this group {group_dn}")

    search_filter = f'(&(&(objectClass=user)(sAMAccountName=St-{student_id}))(memberOf={main_group_dn}))'
    isExist2 = connect_ldap.search(search_base=domain, search_scope=search_scope, search_filter=search_filter,
                                  attributes=attributes)
    if not isExist2:
        if connect_ldap.extend.microsoft.add_members_to_groups(user_dn,main_group_dn):
            add_to_report(f"Adding user {student_id} to group.{main_group_dn}....")
        else:
            message = f"There is a problem in adding student {student_id} to group {main_group_dn}"
            flash(message)
            add_to_report(message)

def add_to_report(message):
    # message = f"Adding user {student_id}to group....."
    with open("./data/report.txt", 'a') as file:
        file.write(f'\n{message}')
    file.close()

def delete_student(book, connect_ldap):
    """This function will delete a list of students from domain"""
    # domain = 'OU=domain-test-users,DC=mcit-test03,DC=local'
    del_counter=0
    for key in book.values():
        student_id = key.get("StudentID")
        if not domain :
            raise ValueError("Error in setting,Please Define Environment Variables")
        isExist = connect_ldap.search(domain, f'(sAMAccountName=St-{student_id})',
                                      attributes={'objectclass', 'sn', 'cn', 'givenname', 'sAMAccountName'})

        if isExist:
            student_dn = connect_ldap.response[0]['dn']
            if connect_ldap.delete(student_dn):
                del_counter+=1
                add_to_report(f"The {student_id} was deleted")
            else:
                message=f"There is an Error in deleting student :{student_id}"
                flash(message)
                add_to_report(message)
        else:
            message=f"There is no entry for {student_id}"
            flash(message)
            add_to_report(message)
    message = f"{del_counter} students deleted successfuly"
    flash(message)

def modify_student_info(book, connect_ldap):
    """This function will modify a list of students based on filled_info in the list"""

    mod_counter=0
    for key in book.values():
        student_id = key.get("StudentID")
        # cn = f"CN={student_id}"
        if not domain :
            raise ValueError("Error in setting,Please Define Environment Variables")
        isExist = connect_ldap.search(domain, f'(sAMAccountName=St-{student_id})',
                                          attributes={'objectclass', 'sn', 'cn', 'givenname', 'sAMAccountName', 'memberOf',
                                                      'department'})
        if isExist:

            student_dn = connect_ldap.response[0]['dn']
            # print(student_dn)
            cn = connect_ldap.entries[0]['cn']
            old_member_of = connect_ldap.response[0]['attributes']['memberOf'][0]
            attr = {}
            if not (isNaN(key.get("Firstname"))):
                attr['givenName'] = [(MODIFY_REPLACE, [key.get("Firstname")])]
            if not (isNaN(key.get("Lastname"))):
                attr['sn'] = [(MODIFY_REPLACE, [key.get("Lastname")])]
            if not (isNaN(key.get("Email"))):
                attr['mail'] = [(MODIFY_REPLACE, [key.get("Email")])]
            if not (isNaN(key.get("Phone"))):
                attr['telephoneNumber'] = [(MODIFY_REPLACE, [key.get("Phone")])]
            if not (isNaN(key.get("Cohort"))):
                attr['cohortname'] = [(MODIFY_REPLACE, [key.get("Cohort")])]
            if not (isNaN(key.get("Program"))):
                attr['department'] = [(MODIFY_REPLACE, [key.get("Program")])]
            if not (isNaN(key.get("StudentType"))):
                attr['studentType'] = [(MODIFY_REPLACE, [key.get("StudentType")])]
            if not (isNaN(key.get("DateOfBirth"))):

                birthdate = key.get("DateOfBirth")
                lst = ["/", "-"]
                for item in lst:
                    if item in birthdate:
                        birthdate = birthdate.replace(item, '.')
                attr['birthdate'] = [(MODIFY_REPLACE, [birthdate])]

            connect_ldap.modify(student_dn, attr)
            isExist = connect_ldap.search(domain, f'(sAMAccountName=St-{student_id})',attributes={'cn'})
            if isExist:
                cn = connect_ldap.entries[0]['cn']

            if not (isNaN(key.get("Cohort"))):
                cohort = key.get("Cohort")
                ou_l=key.get("OU")
                if not (isNaN(ou_l)):
                    temp_list = [cohort[i:i + 2] for i in range(0, len(cohort), 2)]

                    if (temp_list[1] == 'SW') or (temp_list[1] == "RW"):
                        semester = "W"
                    elif (temp_list[1] == "SF") or (temp_list[1] == "RF"):
                        semester = "F"
                    else:
                        semester = "S"
                    ou_list = [f"Students-{semester}{temp_list[2]}", f"{ou_l}-{semester}{temp_list[2]}", f"{cohort}"]

                    create_ous(cohort, connect_ldap,ou_list)

                    ou_dn = f'ou={ou_list[2]},ou={ou_list[1]},ou={ou_list[0]}'
                    new_ou_dn = f'{ou_dn},{domain}'

                    # change the dn~~move to another Organizational unit

                    moveisDone = (connect_ldap.modify_dn(dn=student_dn,relative_dn=f"CN={cn}", new_superior=new_ou_dn))
                # print(f"moveisDone ?:{moveisDone}")
                    new_student_dn = f'cn={cn},{new_ou_dn}'
                    # remove member from previous group
                    removeisDone = connect_ldap.extend.microsoft.remove_members_from_groups(new_student_dn, old_member_of)
                # print(f"remove is done ? :{removeisDone}")
                    create_student_group( cn, student_id, connect_ldap,ou_list)

                    if removeisDone and moveisDone:
                        mod_counter+=1
                        flash(f"The information of {student_id} has been modified!")
                        add_to_report(f"The information of {student_id} has been modified!")

                    else:
                        message="There is an error in Modify function"
                        flash(message)
                        add_to_report(message)
                else:
                    message = "There is no OU in csv file"
                    flash(message)
                    add_to_report(message)
        else:
            message=f"There is no {student_id} in {domain}. "
            flash(message)
            add_to_report(message)
    message = f"{mod_counter} students modified successfuly"
    flash(message)
def isNaN(num):
    """This function will delete if a variable in NAN or not"""
    return num != num

def password_generator():
    alphabet = string.printable
    password = ''.join(secrets.choice(alphabet) for i in range(20))
    password = ''.join(password.split())
    return password

def search_student(student_id, connect_ldap):
    """This function will display the information of a student
    if it exists"""
    # domain = 'OU=domain-test-users,DC=mcit-test03,DC=local'
    search_scope = SUBTREE
    attributes = {'givenName', 'sn', 'sAMAccountName', 'mail', 'telephoneNumber',
                  'department', 'birthdate', 'cohortname', 'userAccountControl','studentType','cohortname'}
    if not domain:
        raise ValueError("Error in setting,Please Define Environment Variables")
    isExist = connect_ldap.search(search_base=domain, search_scope=search_scope,
                                      search_filter=f'(sAMAccountName=St-{student_id})',
                                      attributes=attributes)

    if isExist:
        dict1=connect_ldap.entries[0].entry_attributes_as_dict
        new_key = {'department': 'program',
                   'mail': 'mail',
                   'sn': 'Family',
                   'studentType': 'studentType',
                   'telephoneNumber': 'telephoneNumber',
                   'givenName': 'Name',
                   'birthdate': 'birthdate',
                   'cohortname': 'cohort',
                   'userAccountControl': 'Status',
                   'sAMAccountName': 'Student ID'}

        result=(dict([(new_key.get(key), value) for key, value in dict1.items()]))
        if result['Status'] == [66048]:
            result['Status'] = "enable"
        elif result['Status'] == [66050]:
            result['Status'] = "disable"
    else:
        message=f"There is no student with Student_ID :{student_id}"
        flash(message)
        add_to_report(message)
        result=message
    return result

def enable_disable_student(book, connect_ldap):
    """This function will  toggle (enable/disable) a student status"""
    # *************************************
    # global current_description, Reason, receiver_email_address, student_family, message_route, student_name, email_subject
    stat_counter=0
    for key in book.values():
        receiver_email_address=None
        student_id = key.get("StudentID")
        status = key.get("Status")
        Reason = key.get("Revoking Codes")
        # cn = f"CN={student_id}"
        current_status = 0
        search_scope = SUBTREE
        attributes = {'givenName', 'sn', 'sAMAccountName', 'mail', 'telephoneNumber',
                      'department', 'physicalDeliveryOfficeName', 'description', 'userAccountControl'}
        if not domain :
            raise ValueError("Error in setting,Please Define Environment Variables")
        isExist = connect_ldap.search(search_base=domain, search_scope=search_scope,
                                          search_filter=f'(sAMAccountName=St-{student_id})',
                                          attributes=attributes)
        if isExist:
            student_dn = connect_ldap.response[0]['dn']
            for i in connect_ldap.entries:
                current_status = i.userAccountControl.values[0]
                if not (isNaN(i.mail)):
                    receiver_email_address = i.mail
                else:
                    receiver_email_address = None
                student_name = i.givenName
                student_family = i.sn
                # current_description = i.description.values[0]
                    # status = new_status
            if current_status == 66048:  # if the user is enable
                if status == "disable":
                    attr={'userAccountControl': [(MODIFY_REPLACE, [66050])],
                     'description': [(MODIFY_REPLACE, [Reason])]}
                    if connect_ldap.modify(student_dn, attr):
                        stat_counter = +1
                        message = f"The user {student_id} has been disabled successfully"
                        if Reason == "PAY":
                            message_route = 'templates/Revoke_PAY.html'
                        elif Reason == "DOC":
                            message_route = 'templates/Revoke_DOC.html'
                        email_subject = "Revoke access"
                        if receiver_email_address is not None:

                            message_content = prepare_email_students(message_route=message_route,
                                                             student_name=student_name, student_family=student_family,
                                                             student_id=None, password=None,
                                                             cohort=None, program=None)
                            send_email(receiver_email_address, email_subject, message_content)

                        else:
                            message=f"Student {student_id} does not have email in his/her profile "
                        # add_to_report(message)
                        # flash(message)
                    else :
                        message=f"There is an error in diabling student{student_id}"
                else:
                    message = f"Student {student_id} is currently enabled"

            elif current_status == 66050:  # if the user is disable
                if status == "enable":
                    attr = {'userAccountControl': [(MODIFY_REPLACE, [66048])]}
                    attr['description'] = [(MODIFY_REPLACE, [""])]
                    if connect_ldap.modify(student_dn, attr):
                        stat_counter=+1
                        message = f"The user {student_id} has been enabled successfully"
                        add_to_report(message)
                        message_route = 'templates/Grant_message.html'
                        email_subject = "Grant access"
                        if receiver_email_address is not None:
                            message_content = prepare_email_students(message_route=message_route,
                                                             student_name=student_name, student_family=student_family,
                                                             student_id=None, password=None,
                                                             cohort=None, program=None)
                            send_email(receiver_email_address, email_subject, message_content)
                        else:
                            message=f"Student {student_id} does not have email in his/her profile "
                    else :
                        message=f"There is an error in diabling student{student_id}"
                else:
                    message = f"Student {student_id} is currently disabled"
                add_to_report(message)
            # flash(message)

        else:
            message=f"There is no student with Student_ID :{student_id}"
            # flash(message)
            add_to_report(message)
    message = f"status of {stat_counter} students toggled successfuly"
    flash(message)
def search_student_in_cohort(cohort, connect_ldap):
    """This function will display a list of students in a specific cohort"""
    search_filter_student = f'(objectClass=user)'
    search_filter_ou=f'(&(objectClass=organizationalUnit)(name={cohort}))'
    search_scope = SUBTREE

    isExistOU=connect_ldap.search(search_base=domain, search_filter=search_filter_ou, search_scope=search_scope,
                                      attributes={'ou','distinguishedName'})
                                        # attributes = ALL_ATTRIBUTES)
    if isExistOU:
        ou_dn = connect_ldap.response[0]['attributes']['distinguishedName']
        isExistuser = connect_ldap.search(search_base=ou_dn, search_filter=search_filter_student,
                                              search_scope=search_scope,
                                              attributes={'givenName', 'sn', 'sAMAccountName'})
        if isExistuser:
            raw_result = connect_ldap.response
            result=[]
            for student in raw_result:
                dict1=student['attributes']
                new_key = {'sAMAccountName': 'Student ID',
                           'givenName': 'Name',
                           'sn': 'Family'}
                list = (dict([(new_key.get(key), value) for key, value in dict1.items()]))
                result.append(list)
        else:
            result = f"There is no student in this cohort :{cohort}"
            add_to_report(result)
        return result
    elif not isExistOU:
        result = f"There is not a cohort named {cohort}"
        add_to_report(result)
        return result


def send_email(receiver_email_address, email_subject, message):
    # configure email headers
    message['Subject'] = email_subject
    message['From'] = college_email_address
    message['To'] = receiver_email_address

    server = smtplib.SMTP(email_smtp, 587)
    # identify this client to the SMTP server
    server.ehlo()
    server.starttls()
    # login to email account
    server.login(college_email_address, college_email_password)
    # send email
    # server.send_message(message)
    add_to_report(f"Email has been sent to {receiver_email_address}")
    # close connection to server
    server.quit()

def prepare_report(connect_ldap):
    receiver_email=""
    if not domain:
        raise ValueError("Error in setting,Please Define Environment Variables")
    user=connect_ldap.extend.standard.who_am_i()
    splited_user = user.split('\\')
    user_name = splited_user[1]
    add_to_report(f'Current_user={user_name}')
    if (connect_ldap.search(domain, f'(sAMAccountName={user_name})',
                        attributes={'mail','sAMAccountName'})):
        receiver_email = connect_ldap.response[0]['attributes']['mail']
    message1 = EmailMessage()
    message1.set_content("Please download the attachement as your report")
    message1.add_attachment(open("./data/report.txt", "r").read(), filename="report.txt")
    # print(message1)
    return receiver_email, message1


def prepare_email_students(message_route, student_name, student_family, student_id, password, cohort, program):
    file_content = open(message_route, encoding="utf8").read().format(Lastname=student_family, Firstname=student_name,
                                                                      student_id=student_id, password=password,
                                                                      cohort=cohort, program=program)
    message = EmailMessage()
    # add message content as html type
    message.set_content(file_content, subtype='html')
    return message

