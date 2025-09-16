// Minimal Node.js example (optional)
require('dotenv').config();
const { Client, Intents } = require('discord.js');
const { Configuration, OpenAIApi } = require('openai');
const client = new Client({ intents: [Intents.FLAGS.GUILDS, Intents.FLAGS.GUILD_MESSAGES] });
const conf = new Configuration({ apiKey: process.env.OPENAI_API_KEY });
const openai = new OpenAIApi(conf);
client.on('ready', () => console.log('Node bot ready'));
client.on('messageCreate', async (msg) => {
  if (msg.author.bot) return;
  if (msg.content.startsWith('!ask ')) {
    const q = msg.content.slice(5);
    const r = await openai.createChatCompletion({ model:'gpt-3.5-turbo', messages:[{role:'user', content:q}] });
    msg.reply(r.data.choices[0].message.content);
  }
});
client.login(process.env.DISCORD_TOKEN);
