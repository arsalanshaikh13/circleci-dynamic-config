#!/bin/bash

# Check if an argument was provided.
if [ "$#" -eq 0 ]; then
    echo "Error: No template file specified."
    echo "Usage: $1 <path_to_template_file>"
    exit 1
fi
# Define the path to your template file.
TEMPLATE_FILE=$1

# Check if the template file exists.
if [! -f "$TEMPLATE_FILE"]; then
    echo "Error: Template file '$TEMPLATE_FILE' not found!"
    exit 1
fi

# Read the content of the template file from the file into a variable
TEMPLATE_CONTENT=$(cat "$TEMPLATE_FILE")

# Define the array of folders where the files will be created.
FOLDERS=("build" "release" "package" "compile" "test" "deploy")
# pass the folder names as argument which are stored inside the array, shift command is used to shift the position arguments
# shift
# FOLDERS=("$1" "$2" "$3" "$4" "$5" "$6") or FOLDER=("$@")

# Loop through each folder name in the array.
for folder in "${FOLDERS[@]}"; do
    # Create the directory if it doesn't exist. The -p flag prevents errors if the folder is already there.
    if [ ! -d "$FOLDER" ]; then
        echo "Creating folder: $FOLDER"
        mkdir -p "$FOLDER"
    fi
    
    # Construct the filename in the format "folder-gitlab-ci.yml".
    filename="${folder}-gitlab-ci.yml"
    
    # Create the empty file inside the new folder.
    # touch "$folder/$filename"
    # rm "$folder/$filename"

    # Replace "compile" with the folder name and write to the new file.
    # echo "$TEMPLATE_CONTENT" | sed "s/compile/$folder/g" > "$folder/$filename"
    echo "$TEMPLATE_CONTENT" | awk -v repl="$folder" '
    {
        # lowercase
        gsub(/compile/, repl)

        # Capitalize
        # substr(repl,1,1) extract first letter and only 1 length/occurence ie just the letter itself and not the rest of the letters in the word
        # substr(repl,2) extract all the letters in the word starting from 2nd position
        gsub(/Compile/, toupper(substr(repl,1,1)) substr(repl,2))

        # uppercase
        gsub(/COMPILE/, toupper(repl))
        print
    }' > "$folder/$filename"
    # Print a confirmation message.
    echo "Created file: $folder/$filename"
done

echo "All GitLab CI files have been created successfully!"


# #!/bin/bash

# # Define the source file
# SOURCE_FILE="path/to/your/source_file.txt"

# # Array of destination folders and new filenames
# # Format: "folder1:new_name1" "folder2:new_name2"
# DESTINATIONS=("folder1:file_a.txt" "folder2:file_b.txt" "folder3:file_c.txt")

# # Loop through the destinations
# for DEST in "${DESTINATIONS[@]}"; do
#     # Split the string by ":" to get the folder and new name
#     FOLDER=$(echo "$DEST" | cut -d':' -f1)
#     NEW_NAME=$(echo "$DEST" | cut -d':' -f2)

#     # Check if the folder exists
#     if [ ! -d "$FOLDER" ]; then
#         echo "Creating folder: $FOLDER"
#         mkdir -p "$FOLDER"
#     fi

#     # Copy the file
#     cp "$SOURCE_FILE" "$FOLDER/$NEW_NAME"
        
    # echo "$TEMPLATE_CONTENT" | perl -pe '
    #     use feature "fc";
    #     my $repl = "'$folder'";
    #     s/\bcompile\b/ $repl /gie;
    #     s/\bcompile\b/ 
    #         join "", map {
    #             substr($repl, $_, 1) =~ s/(.)/$1/;
    #             substr($_, 0, 1) =~ /[A-Z]/ ? uc($1) : lc($1)
    #         } 0 .. length($repl)-1
    #     /gie;
    # ' > "$folder/$filename"

#     echo "Copied $SOURCE_FILE to $FOLDER/$NEW_NAME"
# done

# echo "Script finished."
