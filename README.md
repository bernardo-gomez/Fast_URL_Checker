# Fast_URL_Checker

This is a python-based script that receives URLs and performs GET requests.
There are three optimizations:
   - It ignores duplicated URLs;
   - It uses a 10-second HTTP timeout (default value);
   - It runs six concurrent processes ( default value).
 
 This URL checker also ignores URLs that partially match
 strings listed in the "exclude" file. check_url.cfg defines the pathname 
 to the "exclude" file. Example in the exclude file:
 
  https://mail.library.emory.edu/cgi-bin/
  
  URL checker will ignore all URLs in the cgi-bin directory.
  
 
 This package assumes that the input file is an ALMA CSV file.
  Example:
  
  Bibliographic Record,99930303,https://mail.library.emory.edu/uhtbin/echo 
  
  Portfolio,99230003,http://pid.emory.edu/rg0b3
  
  This URL checker resolves emory-formatted persistent URLs (PURLs) to check
  the target URL. Example of a PURL: http://pid.emory.edu/rg0b3 
  
  The outcome of the URL checking is collated into different files according to
  the resource type ("Bibliographic" or "Portfolio") and to the error type and each file
  is mailed to receipients listed on the mailing list defined in check_url.cfg 
  Example of a mailing list file:
  
    1|Bibliographic|someone@yourplace.edu,anotherperson@yourplace.edu
    2|Portfolio|anothermailbox@yourplace.edu,staffmember@yourplace.edu
  
  
  **Files**:
  
  -  checkurl_bib_portolio.sh (it process an ALMA input file before invoking the url checker )
       
  -  parse_cvs.c (it converts the ALMA file into a custom text file)
       Example of custom format:
       https://mail.library.emory.edu/uhtbin/echo_|_99930303_|_1
       
       https://pid.emory.edu/rg0b3_|_99230003_|_2 
  -  environ ( it contains the unix environment to support crontab jobs. environ is based on /usr/bin/env)
  
   
  -  check_url.py ( it reads a custom text file with URLs; divides the file into
       chunks to create concurrent processes)
  
  -   check_url.cfg ( configuration file for check_url.py )
  
