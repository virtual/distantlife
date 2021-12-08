import csv
import sys

# Open the CSV file and read its contents into memory
def save_words(csvf):
  words = []
  headings = []

  with open(csvf, "r") as file:
      reader = csv.reader(file, delimiter=',')

      # Create dictionary keys
      for row in reader:
          i = 0
          while (i < len(row)):
              headings.append(row[i])
              i += 1
          break

      # Save STR values to each person
      # lost in space
      for row in reader:
          i = 0
          word = {}

          while (i < len(row)):
              key = str(headings[i])
              value = row[i]
              word[key] = value
              i += 1
          words.append(word)

  # Loop thru types
  for w in range(1, len(words)):
      pkey = headings[i]
      print(pkey, " ", w) 

  file.close()