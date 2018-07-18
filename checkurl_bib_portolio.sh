#!/bin/bash

##
##  check_bib_portfolio_url.sh reads a designated ALMA CSV file;  
##    it converts the file to a text file compatible with check_url.py;
##    and it feeds the text file to the url checker ( check_url.py) .
## example of lines from the CSV file:
# Bibliographic Record,990016345870302486,http://purl.access.gpo.gov/GPO/LPS125131
# Portfolio,53284293680002486,http://purl.access.gpo.gov/GPO/LPS125131
#
# corresponding lines to feed into check_url.py:
# http://purl.access.gpo.gov/GPO/LPS125131_|_990016345870302486_|_1
# http://purl.access.gpo.gov/GPO/LPS125131_|_532842936800024866_|_2

##   author: bernardo gomez 
##   date: february, 2018


input_dir=/Users/bernardo/develop/   ### your dir here
work_dir=/Users/bernardo/develop/integrations/urlCheck/work/   ## your dir here
bin_dir=/Users/bernardo/develop/   ## your dir here

config_dir="/Users/bernardo/develop/"    ## your dir here 
. ${config_dir}environ    # dot in environ variables

# export all of the environ variables to my children
for env_var in $(cat ${config}environ | awk -F'=' '{print $1}')
do
  export ${env_var}
done

file=alma_csv_file    #### your alma file here
# change Bibliographic Record to "1"
# change Portfolio to "2"
 
  if [ ! -s ${file} ]; then
      echo "alma text file doesn't exist" >&2
      exit 1
  fi
  cat  ${file}| ${bin_dir}/parse_csv -d","  |\
  sed 's/\(.*\)_\|_\(.*\)_\|_\(.*\)/\3_\|_\2_\|_\1/g' | sed 's/Bibliographic Record/1/g'|\
  sed 's/Portfolio/2/g'| sort -u  > ${work_dir}input_all_urls

  if [ -s ${work_dir}/input_all_urls ]; then
    cat  ${work_dir}input_all_urls |\
    ${bin_dir}/check_url.py  ${config_dir}check_url.cfg  2> ${work_dir}checkurl_log 
    status=$?

    if [ ${status} -eq 0 ]; then
       filename=$(basename ${file})
       mv  ${file} ${input_dir}done_${filename}     ## rename original alma file.
    else
      echo "url checker failed" >&2
      exit 1
    fi
  else
      echo "conversion from alma format to custom format failed" >&2
  fi
  exit 0
