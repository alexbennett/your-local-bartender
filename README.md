# Bartender Discord Bot

The Bartender Discord Bot is a Python program that acts as a virtual bartender in a Discord server. It can generate images, convert text to speech, and provide conversational responses based on user input.

## Features

- **Image Generation**: The bot can generate images based on a prompt using the OpenAI API.

- **Text-to-Speech**: The bot can convert text messages to speech using the Google Text-to-Speech (gTTS) library and play the generated audio in the voice channel.

- **Conversational AI**: The bot can listen to user input, generate conversational responses using the OpenAI Chat Completions API, and maintain conversational context.

- **Command Prefix**: The bot listens for commands with a specified prefix and performs the corresponding actions.

## Setup

To set up and run the Bartender Discord Bot, follow these steps:

1. Clone the repository or download the source code files to your local machine.

2. Install the required Python packages by running the following command:

   ```
   pip install -r requirements.txt
   ```

3. Set up a Discord bot account and obtain the bot token. Refer to the Discord API documentation for instructions.

4. Create a `config.py` file in the same directory as the Python files. Add the following content to the file:

   ```python
   # Discord Bot Token
   DISCORD_BOT_TOKEN = "YOUR_DISCORD_BOT_TOKEN"

   # OpenAI API Key and Model
   OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
   OPENAI_MODEL = "YOUR_OPENAI_MODEL"
   ```

   Replace `YOUR_DISCORD_BOT_TOKEN` with your Discord bot token and `YOUR_OPENAI_API_KEY` and `YOUR_OPENAI_MODEL` with your OpenAI API key and model.

5. Customize the configuration variables in the `bartender.py` file according to your preferences:

   - `CONFIG_CHANNEL`: The name of the Discord voice channel where the bot will join.
   - `COMMAND_PREFIX`: The prefix for bot commands.
   - `COMMANDS_PIC`, `COMMANDS_BARTENDER`, `COMMANDS_SAY`, `COMMANDS_READ`, `COMMANDS_PLAY`, `COMMANDS_CLEAR`: The command strings for different bot functionalities.

6. Run the `bartender.py` file using the following command:

   ```
   python bartender.py
   ```

7. Invite the bot to your Discord server using the OAuth2 URL generated for your bot account. Refer to the Discord API documentation for instructions on inviting bots.

8. Interact with the bot in your Discord server by using the configured command prefix and the supported commands.

Make sure to replace `YOUR_DISCORD_BOT_TOKEN`, `YOUR_OPENAI_API_KEY`, and `YOUR_OPENAI_MODEL` with your own values in the `config.py` file and update any other sections or instructions as needed.

Let me know if you need any further assistance!

## Command Reference

- `>bartender`: Starts a conversation with the bot.

- `>say <message>`: Converts the provided `<message>` to speech and plays it in the voice channel.

- `>listen <phrase>`: Makes the bot listen to the provided `<phrase>`, generates a response, and potentially plays a TTS audio response in the voice channel.

- `>pic <prompt>`: Generates images based on the provided `<prompt>` and sends them as responses in the Discord channel.

- `>clear`: Clears a specified number of messages in the channel where the command is invoked.

## Contributions

Contributions to the Bartender Discord Bot project are welcome! If you have any ideas, improvements, or bug fixes, feel free to open an issue or submit a pull request.

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for more information.