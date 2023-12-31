import glob
import unittest
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
import time
import os

RESPONSES_DIR = 'responses'
ASSISTANTS_FILE_NAME = 'assistants.txt'
FINAL_PROPOSAL_FILE_NAME = 'final_proposal.txt'
PROPOSAL_FILE_NAME_PATTERN = '*_proposal.txt'

ASSISTANT_ID_DECISION = os.getenv('ASSISTANT_ID_DECISION')
ASSISTANT_ID_GET_PROPOSALS = os.getenv('ASSISTANT_ID_GET_PROPOSALS')
ASSISTANT_ID_CREATE_ASSISTANTS = os.getenv('ASSISTANT_ID_CREATE_ASSISTANTS')


def get_scenario_input():
    with open('scenario_input.txt', 'r') as file:
        file_content = file.read()

    return file_content


def wait_for_run_completion(client, thread, run):
    run_status = ''
    attempts = 0
    max_attempts = 15
    while True:
        try:
            run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if run_status.status in ['completed', 'failed']:
                break
            if attempts >= max_attempts:
                break
            time.sleep(5)
            attempts += 1
        except Exception as e:
            print(f"Attempt {attempts + 1} failed: {e}")
            break
    return run_status


def get_proposal_filenames(directory):
    file_pattern = os.path.join(directory, PROPOSAL_FILE_NAME_PATTERN)

    proposal_files = glob.glob(file_pattern)

    filenames = [os.path.basename(file_path) for file_path in proposal_files]

    return filenames


def read_files(file_names):
    file_contents = []
    for file_name in file_names:
        full_path = os.path.join(RESPONSES_DIR, file_name)
        try:
            with open(full_path, 'r') as file:
                file_contents.append(file.read())
        except FileNotFoundError:
            print(f"File {file_name} not found.")
        except Exception as e:
            print(f"An error occurred while reading {file_name}: {e}")
    return "\n\n".join(file_contents)


class TestCreateAssistant(unittest.TestCase):

    def setUp(self):
        _ = load_dotenv(find_dotenv())
        self.client = OpenAI()

    # topology:
    # message is a single, well, message
    # thread contains messages
    # run takes the assistant and thread

    def test_get_decision(self):
        client = OpenAI()

        scenario = get_scenario_input()

        file_names = get_proposal_filenames(RESPONSES_DIR)

        combined_contents = read_files(file_names)
        print(combined_contents)

        thread = client.beta.threads.create()
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=scenario + "\r\n" + combined_contents
        )
        run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=ASSISTANT_ID_DECISION)
        run_status = wait_for_run_completion(client, thread, run)

        if run_status.status == 'completed':
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            print(messages)
            with open(os.path.join(RESPONSES_DIR, FINAL_PROPOSAL_FILE_NAME), 'w') as file:
                file.write(messages.data[0].content[0].text.value)

    def test_get_proposals(self):
        client = OpenAI()

        start_delim = '***START PERSONA***'
        end_delim = '***END PERSONA***'
        delimiter = "***PERSONA*** "

        scenario = get_scenario_input()

        with open(os.path.join(RESPONSES_DIR, ASSISTANTS_FILE_NAME), 'r') as file:
            lines = file.readlines()

        personas = []
        current_persona = ''
        recording = False

        for line in lines:
            if start_delim in line:
                recording = True
                current_persona = ''
            elif end_delim in line:
                recording = False
                personas.append(current_persona.strip())
            elif recording:
                current_persona += line

        entries_with_delimiter = [delimiter + persona for persona in personas if persona.strip()]

        for i, entry in enumerate(entries_with_delimiter):
            print(entry.strip())

            thread = client.beta.threads.create()
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=scenario + "\r\n" + entry
            )
            run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=ASSISTANT_ID_GET_PROPOSALS)

            run_status = wait_for_run_completion(client, thread, run)

            if run_status.status == 'completed':
                messages = client.beta.threads.messages.list(
                    thread_id=thread.id
                )
                print(messages)
                with open(os.path.join(RESPONSES_DIR, f'{i}_proposal.text'), 'w') as file:
                    file.write(messages.data[0].content[0].text.value)

    def test_create_assistants(self):
        client = OpenAI()

        create_assistants = "Create three personas for AI assistants. I want the result to be a diverse group of personas, who each can provide different viewpoints. "
        scenario = get_scenario_input()

        thread = client.beta.threads.create()
        _ = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=create_assistants + scenario
        )

        run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=ASSISTANT_ID_CREATE_ASSISTANTS)
        run_status = wait_for_run_completion(client, thread, run)

        if run_status.status == 'completed':
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            print(messages)
            with open(os.path.join(RESPONSES_DIR, ASSISTANTS_FILE_NAME), 'w') as file:
                file.write(messages.data[0].content[0].text.value)

