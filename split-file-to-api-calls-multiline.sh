#!/bin/bash

if [[ $# -ne 2 ]] ; then
    echo 'Wrong number of arguments.  Arguments should be <input_filename> <output_filename>.'
    exit 1
fi

INPUT_FILENAME=./$1
OUTPUT_FILENAME=./$2

TMP_FOLDER=./tmp

mkdir -p ${TMP_FOLDER}

rm ${TMP_FOLDER}/*

echo "#!/bin/bash" > ${OUTPUT_FILENAME}
echo "" >> ${OUTPUT_FILENAME}
echo "" >> ${OUTPUT_FILENAME}

echo "# Edit these values #" >> ${OUTPUT_FILENAME}
echo "USERNAME=<USERNAME>" >> ${OUTPUT_FILENAME}
echo "API_KEY=<API_KEY>" >> ${OUTPUT_FILENAME}
echo "HOST=<HOST>" >> ${OUTPUT_FILENAME}

echo "" >> ${OUTPUT_FILENAME}
echo "" >> ${OUTPUT_FILENAME}

split -l 4 --numeric-suffixes ${INPUT_FILENAME} ${TMP_FOLDER}/chunk

for chunk_file in ${TMP_FOLDER}/*
do
        #echo "tmp_file: ${tmp_file}"
        LINE_COUNT=$(wc -l < ${chunk_file})
        #echo "- ${LINE_COUNT} -"
        if [[ ${LINE_COUNT} == "4" ]]
        then
                REPO_NAME=$(sed -n 1p ${chunk_file} | tr -d '"') # Extract the first line and remove double quotes.
                REPO_NAME=${REPO_NAME%?} # Remove trailing comma
                REPO_PATH=$(sed -n 2p ${chunk_file} | tr -d '"')
                REPO_PATH=${REPO_PATH%?}
                REPO_FILE=$(sed -n 3p ${chunk_file} | tr -d '"')
                REPO_FILE=${REPO_FILE%?}
                REPO_HASH=$(sed -n 4p ${chunk_file} | tr -d '"')
                #echo "REPO: ${REPO_NAME}, PATH: ${REPO_PATH}, FILE: ${REPO_FILE}, HASH: ${REPO_HASH}"
                if [[ ${REPO_PATH} == *"_uploads"* ]];
                then
                        #echo "Contains _uploads, skipping"
                        /bin/true
                else
                        #echo "Appending API call"
                        # Update this curl command to change which API is being called.  This version just downloads the artifact.
                        echo "curl -u '\${USERNAME}:\${API_KEY}' https://\${HOST}/artifactory/${REPO_NAME}/${REPO_PATH}/${REPO_FILE}" >> ${OUTPUT_FILENAME}
                fi
        fi
done
