#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
     this script reads URLs from a text file and performs HTTP GET 
     requests to test the URLs.
     the script expects a configuration file on the command line.
      configuration entries are:

      process_count,
      timer,
      in_file,
      temp_directory,
      exclude,
      mailing_list,
      smtp_server,
      from_mail
          "process_count" is the number of concurrent processes that
          perform the HTTP requests.
          "timer" is the number of seconds allowed to the request.
          "in_file" is the text file that contains the URLs.
             a line in the in_file is:
             URL_|_alma_mms_id_|_resource_type
                resource_type=1 for Bibliographic record,
                resource_type=2 for Portfolio record
          "temp_directory" is the directory where the work files will go.
          "exclude" is the text file that contains the URLs or part of URLs 
           that should be ignored.
          "mailing_list" is the file that contains the recipients of the 
          failed URLs according to  the resource_type (bibliographic 
          or portfolio) 
         "smtp_server" is the hostame that mails out the results.
         "from_mail" is the email address of the sender.
      the results reflect ALMA's records type: bibliographic or portfolio.
"""
__author__ = 'bernardo gomez'
__date__ = 'june 2018'

import time
import random
import requests
import re
import subprocess
import sys
import os
# emory would need it
#import socks
import socket
from multiprocessing import Process, Lock
import smtplib
from email.mime.text import MIMEText

# URL_@_record_id_@_resource_type

def send_email(smtp_server,recipients,from_mail,body,subject):
   """
      it receives the necessary parameters to send an email message.
      parameters:
        smtp_server = outbound mail server.
        recipients = email addresses separated by ","
        from_mail = email sender (e.g. do-not-reply@myplace.edu )
        body = email message body with results.
        subject =  email subject line.
   """
   email_list=recipients.split(",")
   msg = MIMEText(body,'plain','utf-8')

   msg['Subject'] = subject
   msg['From'] = from_mail
   msg['To'] = recipients
   try:
      s = smtplib.SMTP(smtp_server,timeout=10)
   except:
      sys.stderr.write("**ERROR: couldn't connect to smptp server\n")
      return 1
   s.sendmail(from_mail, email_list, msg.as_string())
   s.quit()
   return 0


def report_URL(mms_id,resource_type,target,email_body):
    """
        it adds a string with results to the email_body list identified
        by the resource type (typically ALMA bib or ALMA portfolio )
    """
    email_body[int(resource_type)]+=target+" mms_id: "+str(mms_id)+"\n"
    return

def decode_message(message):
       """
          message is the string produced by an HTTP  exception.
          the function parses the message to extract an error type.
          the error type is encoded as 6XX ( a local convention).
       """
       hostname=re.compile(".*(Failed to establish a new).*")
       my_timeout=re.compile(".*( Read timed out).*")
       no_protocol=re.compile(".*(No connection adapters).*")
       no_scheme=re.compile(".*(No schema supplied).*")
       no_connection=re.compile(".*(Connection to ).*(timed out).*")
       s=hostname.search(message)
       if s:
          return "603"
       s=my_timeout.search(message)
       if s:
          return "605"
       s=no_protocol.search(message)
       if s:
          return "607"
       s=no_scheme.search(message)
       if s:
          return "609"
       s=no_connection.search(message)
       if s:
          return "610"
       return "608"

def process_file(number,directory,input_prefix,output_prefix,timer,exclusion):
    """
      this function opens the designated text file that contains the URLs
      and invokes the GET method to test the URL.
      parameters:
          number = the thread id (0,1..)
          directory = work directory.
          input_prefix =  part of the input file name.
          output_prefix  = part of the output file name.
          timer = HTTP timeout.
          exclusion = file with strings for URLs to ignore.
    """
    delim="_|_"
    pause = random.randint(3,8)
    # use lock when printing to standard output.
    lock=Lock()
    sequence='{:04d}'.format(int(number))
    output_file=directory+output_prefix+sequence
    input_file=directory+input_prefix+sequence

    try:
        output_f=open(output_file,'w')
    except:
        lock.acquire()
        print "failed to open "+output_file
        lock.release()
        return
    try:
        input_f=open(input_file,'r')
    except:
        lock.acquire()
        print "failed to open "+input_file
        lock.release()
        return
    ## resolve local PURLs. emoy libraries use pid.emory.edu
    emory_pid=re.compile("(http|https)(://pid.emory.edu/)(.*)")

    ## pid would containg an ezproxy URL. get ezproxy's target for testing.
    ezproxy=re.compile(".*\?url=(.*)")

    # use 'previous_url' to detect duplicate URLs.
    previous_url="----"
    try:
     for i_line in input_f:
        i_line=i_line.rstrip("\n")
        try:
            url,mms_id,record_type=i_line.split(delim)
        except:
            sys.stderr.write("**ERROR: invalid input line.\n")
            continue
        skip_it=False
        ## if URL contains an excluded string then
        ## do not test the URL.
        for x_string in exclusion:
            if url.find(x_string) > -1:
                skip_it=True
                break
        if skip_it:
            continue
        if url == previous_url:
           continue
        ####  ugly hack to allow HTTPS requests out of turing.
        #socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 8080)
        #socket.socket = socks.socksocket
        ####
        previous_url=url
        m=emory_pid.match(url)
        if m:
           if m.group(1) == "http":
                new_emorypid="https"+m.group(2)+m.group(3)
           else:
                new_emorypid=url
           try:
              response = requests.get(new_emorypid, timeout=int(timer),allow_redirects=False)
           except Exception as e:
             message=str(e)
             return_code=decode_message(message)
             if return_code == "605":
                output_f.write("HTTP/1.1_@_605_@_connection timed out_@__@_"+i_line+"\n")
                continue
             if return_code == "603":
                output_f.write("HTTP/1.1_@_603_@_unknown hostname_@__@_"+i_line+"\n")
                continue
             if return_code == "607":
                output_f.write("HTTP/1.1_@_607_@_unsupported HTTP protocol_@__@_"+i_line+"\n")
                continue
             if return_code == "609":
                output_f.write("HTTP/1.1_@_609_@_Ill-formed URL_@__@_"+i_line+"\n")
                continue
             if return_code == "610":
                output_f.write("HTTP/1.1_@_610_@_Connection to server failed_@__@_"+i_line+"\n")
                continue
             if return_code == "608":
                output_f.write("HTTP/1.1_@_608_@_Unknown Python exception_@__@_"+i_line+"\n")
                continue
           status=response.status_code
           if status == 301 or status == 302:
#sys.stdout.write("HTTP/1.1_@_"+str(http_code)+"_@_"+str(description)+"_@_ _@_"+i_line+"\n")
               headers=response.headers
               redirection=headers["Location"]
               mezp=ezproxy.match(redirection)
               if mezp:
                   url=mezp.group(1)
           elif status > 399:
              output_f.write("HTTP/1.1_@_"+str(status)+"_@_"+"_@_"+"_@_"+i_line+"\n")
              continue
        try:
            response = requests.get(url, timeout=int(timer),allow_redirects=False)
        except Exception as e:
            message=str(e)
            return_code=decode_message(message)
            if return_code == "605":
                output_f.write("HTTP/1.1_@_605_@_connection timed out_@__@_"+i_line+"\n")
                continue
            if return_code == "603":
                output_f.write("HTTP/1.1_@_603_@_unknown hostname_@__@_"+i_line+"\n")
                continue
            if return_code == "607":
                output_f.write("HTTP/1.1_@_607_@_unsupported HTTP protocol_@__@_"+i_line+"\n")
                continue
            if return_code == "609":
                output_f.write("HTTP/1.1_@_609_@_Ill-formed URL_@__@_"+i_line+"\n")
                continue
            if return_code == "610":
                output_f.write("HTTP/1.1_@_610_@_Connection to server failed_@__@_"+i_line+"\n")
                continue
            if return_code == "608":
                output_f.write("HTTP/1.1_@_608_@_Unknown Python exception_@__@_"+i_line+"\n")
                continue
            continue
        status = response.status_code
        if status >  300 and status < 399:
            headers=response.headers
            redirection=headers["Location"]
            continue
        if status > 399:
             output_f.write("HTTP/1.1_@_"+str(status)+"_@_"+"_@__@_"+i_line+"\n")
             continue
    except:
        lock.acquire()
        print "**ERROR "+str(i_line)
        lock.release
    output_f.close()
    input_f.close()
    return



if __name__ == '__main__':
    #  it expects a configuration file in the command line.

    os.environ["LANG"]="en_US.utf8"
    if len(sys.argv) < 2:
      sys.stderr.write("usage:" +sys.argv [0]+" config_file"+"\n")
      sys.stderr.write("configuration file entries:"+"\n")
      sys.stderr.write("    process_count= number of concurrent HTTP requests."+"\n")
      sys.stderr.write("    in_file= file that holds the URLs."+"\n")
      sys.stderr.write("    timer= HTTP timeout in seconds."+"\n")
      sys.stderr.write("    temp_directory=directory for work files."+"\n")
      sys.stderr.write("    exclude= file with (partial) URLs to ignore."+"\n")
      sys.stderr.write("    mailing_list= who will receive reports."+"\n")
      sys.stderr.write("    smtp_server= outbound mail server."+"\n")
      sys.stderr.write("    from_mail= email sender."+"\n")
      exit(1)

    try:
       config=open(sys.argv[1],'r')
    except:
      sys.stderr.write("couldn't open config. file:"+sys.argv[1]+"\n")
      exit(1)

    process_count=int(6)   #  default value for concurrent requests is 6.
    timer=int(10)     # default timeout value is 10 seconds.
    in_file=""
    temp_directory=""
    exclude=""
    mailing_list=""
    smtp_server=""
    from_mail=""

    param=re.compile("(.*?)=(.*)")
    for line in config:
      line=line.rstrip("\n")
      m=param.match(line)
      if m:
         if m.group(1) == "process_count":
            process_count=m.group(2)
            process_count=int(process_count)
         if m.group(1) == "timer":
            timer=str(m.group(2))
         if m.group(1) == "in_file":
            in_file=str(m.group(2))
         if m.group(1) == "temp_directory":
            temp_directory=str(m.group(2))
         if m.group(1) == "exclude":
            exclude=str(m.group(2))
         if m.group(1) == "mailing_list":
            mailing_list=str(m.group(2))
         if m.group(1) == "smtp_server":
            smtp_server=str(m.group(2))
         if m.group(1) == "from_mail":
            from_mail=str(m.group(2))

    config.close()
    param_missing=0
    if temp_directory == "":
       sys.stderr.write("work directory not specified\n")
       param_missing+=1
    if mailing_list == "":
       sys.stderr.write("mailing list not specified\n")
       param_missing+=1
    if in_file == "":
       sys.stderr.write("in_file  not specified\n")
       param_missing+=1
    if smtp_server == "":
       sys.stderr.write("smtp_server  not specified\n")
       param_missing+=1
    if from_mail == "":
       sys.stderr.write("from_mail not specified\n")
       param_missing+=1

    if param_missing > 0:
       exit(1)

    procs = []
    exclusion=[]
    try:
        mail_f=open(mailing_list,'r')
    except:
        sys.stderr.write("**ERR: couldn't open mailing_list "+str(mailing_list)+"\n")
        exit(1)
    email_info={}
    # mailing list is indexed by the record type (bibliographic or portfolio).
    # max_number will hold  the highest index.
    # typical mailing list entry:
        #digit|record or resource type|email addresses separated by ","
    max_number=int(0)

    for line in mail_f:
        line=line.rstrip("\n")
        r_type,r_name,mail_address=line.split("|")
        email_info[r_type]=str(r_name)+"|"+mail_address
        if int(r_type) > max_number:
            max_number=int(r_type)
    mail_f.close()

    # get number of text lines in input file.
    line_count=0
    try:
       input_f=open(in_file,'w')
    except:
       sys.stderr.write("**ERR: couldn't create input file"+"\n")
       exit(1)

    try:
       for line in sys.stdin:
          line_count+=1
          input_f.write(line)         
    except:
         pass
    input_f.close()

    #print "line_count:"+str(line_count)

    if line_count == 0:
       sys.stderr.write("**ERR: input file is empty"+"\n")
       exit(1)
  
    if process_count == 0:
       sys.stderr.write("**ERR: process count must not be zero"+"\n")
       exit(1)

    chunk_size=line_count/process_count
    extra_lines=line_count%process_count # (modulo tells us if we need
                            #  an extra process.

   ####  take care of trivial case 
    if chunk_size == 0:
       chunk_size=extra_lines
       process_count=0
   ###  trivial case 

    total_processes=process_count
    if extra_lines > 0:
      total_processes=process_count+1
      process_count=total_processes

    total_processes=int(total_processes)  # make sure that is an integer.
    next_chunk=0
    file_path=temp_directory+"/"+"batch_*"
    batch='{:04d}'.format(next_chunk)
    batch=temp_directory+"/batch_"+batch
    batch=batch.replace("//","/")
       # delete work files ( batch_ and result_ )
    for k in range(total_processes):
         id='{:04d}'.format(k)
         file_path=temp_directory+"batch_"+id
         try:
            os.unlink(file_path)
         except:
            pass

    for k in range(total_processes):
         id='{:04d}'.format(k)
         file_path=temp_directory+"result_"+id
         try:
            os.unlink(file_path)
         except:
            pass
    try:
        output_f=open(batch,'w')
    except:
       sys.stderr.write("**ERR: couldn't open output "+str(batch)+"\n")
       exit(1)

    # divide input file into chunks that are passed to concurrent
    # processes.
    line_count=0
    try:
       input_f=open(in_file,'r')
    except:
       sys.stderr.write("**ERR: couldn't open input file"+"\n")
       exit(1)
    for line in input_f:
        if line_count == chunk_size:
           next_chunk+=1
           output_f.close()
           if next_chunk == total_processes:
               break
           batch='{:04d}'.format(next_chunk)
           batch=temp_directory+"/batch_"+batch
           batch=batch.replace("//","/")
           try:
              output_f=open(batch,'w')
           except:
              sys.stderr.write("**ERR: couldn't open output "+str(batch)+"\n")
              exit(1)
           output_f.write(line)
           line_count=1
        else:
           line_count+=1
           output_f.write(line)
    input_f.close()
    if extra_lines > 0 and total_processes > 1:
           batch='{:04d}'.format(next_chunk)
           batch=temp_directory+"/batch_"+batch
           batch=batch.replace("//","/")
           try:
              output_f=open(batch,'w')
           except:
              sys.stderr.write("**ERR: couldn't open output "+str(batch)+"\n")
              exit(1)
           output_f.write(line)
    output_f.close()
    exclusion=[]
    exclude_OK=True
    # create a list of exclusion strings (partial or total URL).
    if  exclude != "":
      try:
        exclude_f=open(exclude,'r')
      except:
          sys.stderr.write("**ERR: couldn't open exclusion "+str(exclude)+"\n")
          exclude_OK=False
      if exclude_OK:
        for line in exclude_f:
            line=line.rstrip("\n")
            exclusion.append(line)

    # spawn concurrent processes. each process handles a batch
    # of URLs.

    for number in range(total_processes):
        proc = Process(target=process_file, args=(number,temp_directory,"batch_","result_",timer,exclusion,))
        procs.append(proc)
        proc.start()
    # wait until all processes finish.
    for proc in procs:
         proc.join()
    dirs = os.listdir( temp_directory )
    
  ## prepare lists according to the result types from HTTP GETs.

    url_result=re.compile("result_(.*)")
    unknown_hostname=[]
    connection_timedout=[]
    unsupported_HTTP_protocol=[]
    unknown_exception=[]
    ill_formed_url=[]
    connection_failed=[]
    bad_request=[]
    pass_required=[]
    forbidden=[]
    not_found=[]
    internal_error=[]

    for i in range(int(max_number)+1):
        connection_timedout.append("")
    for i in range(int(max_number)+1):
        unknown_hostname.append("")
    for i in range(int(max_number)+1):
        unsupported_HTTP_protocol.append("")
    for i in range(int(max_number)+1):
        unknown_exception.append("")
    for i in range(int(max_number)+1):
        ill_formed_url.append("")
    for i in range(int(max_number)+1):
        connection_failed.append("")
    for i in range(int(max_number)+1):
        bad_request.append("")
    for i in range(int(max_number)+1):
        pass_required.append("")
    for i in range(int(max_number)+1):
        pass_required.append("")
    for i in range(int(max_number)+1):
        forbidden.append("")
    for i in range(int(max_number)+1):
        not_found.append("")
    for i in range(int(max_number)+1):
        internal_error.append("")

#  _@_603_@_unknown hostname_@__@_"+line+"\n")
#  _@_605_@_connection timed out_@__@_"+line+"\n")
#  _@_607_@_unsupported HTTP protocol_@__@_"+line+"\n")
#  _@_608_@_Unknown Python exception_@__@_"+line+"\n")
#  _@_609_@_Ill-formed URL_@__@_"+line+"\n")
#  _@_610_@_Connection to server failed_
  
# read each result file and collate according to result type.
    for k in range(total_processes):
        id='{:04d}'.format(k)
        file_path=temp_directory+"/result_"+id
        try:
             result_f=open(file_path,'r')
        except:
             sys.stderr.write("**ERR: couldn't open input "+str(file_path)+"\n")
             continue
        for line in result_f:
            try:
                 line=line.rstrip("\n")
                 field=line.split("_@_")
                 return_code=int(field[1])
                 url_info=field[4]
                 target,mms_id,resource_type=url_info.split("_|_")
                 if return_code == 603:
                     report_URL(mms_id,resource_type,target,unknown_hostname)  
                 elif return_code == 605:
                     report_URL(mms_id,resource_type,target,connection_timedout)  
                 elif return_code == 607:
                     report_URL(mms_id,resource_type,target,unsupported_HTTP_protocol)  
                 elif return_code == 608:
                     report_URL(mms_id,resource_type,target,unknown_exception)  
                 elif return_code == 609:
                     report_URL(mms_id,resource_type,target,ill_formed_url)  
                 elif return_code == 610:
                     report_URL(mms_id,resource_type,target,connection_failed)  
                 elif return_code == 400:
                     report_URL(mms_id,resource_type,target,bad_request)  
                 elif return_code == 401:
                     report_URL(mms_id,resource_type,target,pass_required)  
                 elif return_code == 403:
                     report_URL(mms_id,resource_type,target,forbidden)  
                 elif return_code == 404 or return_code == 410:
                     report_URL(mms_id,resource_type,target,not_found)  
                 elif return_code == 500:
                     report_URL(mms_id,resource_type,target,internal_error)  
                 elif return_code == 501:
                     report_URL(mms_id,resource_type,target,unsupported_HTTP_protocol)  

            except:
              sys.stderr.write("**ERR: failed to process HTTP results"+"\n")
              continue
        result_f.close()
    #
  # send emails  with results.

    if len(not_found) > 0:
          for entry in not_found:
              rtype_id=not_found.index(entry)
              try:
                    rname,recipients=email_info[str(rtype_id)].split("|")
              except:
                    continue
              subject="[urlchecker "+rname+"] URL not found (nicht gefunden)"
              send_email(smtp_server,recipients,from_mail,entry,subject)
    if len(unknown_hostname) > 0:
          for entry in unknown_hostname:
              rtype_id=unknown_hostname.index(entry)
              try:
                    rname,recipients=email_info[str(rtype_id)].split("|")
              except:
                    continue
              subject="[urlchecker "+rname+"] unknown hostname (unbekannter gastgeber)"
              send_email(smtp_server,recipients,from_mail,entry,subject)
    if len(unsupported_HTTP_protocol) > 0:
          for entry in unsupported_HTTP_protocol:
              rtype_id=unsupported_HTTP_protocol.index(entry)
              try:
                    rname,recipients=email_info[str(rtype_id)].split("|")
              except:
                    continue
              subject="[urlchecker "+rname+"] unsupported HTTP protocol (nicht unterstütztes Protokoll)"
              send_email(smtp_server,recipients,from_mail,entry,subject)
    if len(ill_formed_url) > 0:
          for entry in ill_formed_url:
              rtype_id=ill_formed_url.index(entry)
              try:
                    rname,recipients=email_info[str(rtype_id)].split("|")
              except:
                    continue
              subject="[urlchecker "+rname+"] ill-formed URL"
              send_email(smtp_server,recipients,from_mail,entry,subject)

    #connection_failed
    if len(connection_failed) > 0:
          for entry in connection_failed:
              rtype_id=connection_failed.index(entry)
              try:
                    rname,recipients=email_info[str(rtype_id)].split("|")
              except:
                    continue
              subject="[urlchecker "+rname+"] connection failed"
              send_email(smtp_server,recipients,from_mail,entry,subject)
    #bad_request
    if len(bad_request) > 0:
          for entry in bad_request:
              rtype_id=bad_request.index(entry)
              try:
                    rname,recipients=email_info[str(rtype_id)].split("|")
              except:
                    continue
              subject="[urlchecker "+rname+"] bad HTTP request"
              send_email(smtp_server,recipients,from_mail,entry,subject)
    #permission_required
    if len(pass_required) > 0:
          for entry in pass_required:
              rtype_id=pass_required.index(entry)
              try:
                    rname,recipients=email_info[str(rtype_id)].split("|")
              except:
                    continue
              subject="[urlchecker "+rname+"] permission required"
              send_email(smtp_server,recipients,from_mail,entry,subject)
    #forbidden
    if len(forbidden) > 0:
          for entry in forbidden:
              rtype_id=forbidden.index(entry)
              try:
                    rname,recipients=email_info[str(rtype_id)].split("|")
              except:
                    continue
              subject="[urlchecker "+rname+"] access forbidden"
              send_email(smtp_server,recipients,from_mail,entry,subject)
    #internal_error
    if len(internal_error) > 0:
          for entry in internal_error:
              rtype_id=internal_error.index(entry)
              try:
                    rname,recipients=email_info[str(rtype_id)].split("|")
              except:
                    continue
              subject="[urlchecker "+rname+"] system error"
              send_email(smtp_server,recipients,from_mail,entry,subject)
    #unsupported_HTTP_protocol
    if len(unsupported_HTTP_protocol) > 0:
          for entry in unsupported_HTTP_protocol:
              rtype_id=unsupported_HTTP_protocol.index(entry)
              try:
                    rname,recipients=email_info[str(rtype_id)].split("|")
              except:
                    continue
              subject="[urlchecker "+rname+"] unsupported HTTP protocol"
              send_email(smtp_server,recipients,from_mail,entry,subject)

