const notifications = {
  blocked: { body: "会话阻塞，等待处理", priority: "high" },
  waiting: { body: "会话已完成，等待回复", priority: "high" },
  done: { body: "会话已经彻底完成", priority: "default" },
};
const retryDelays = [1000, 5000, 30000];

const wait = (delay) => new Promise((resolve) => setTimeout(resolve, delay));

async function sendNotification(topic, state, notification) {
  for (let attempt = 0; attempt <= retryDelays.length; attempt += 1) {
    let response;
    try {
      response = await fetch(`https://ntfy.sh/${encodeURIComponent(topic)}`, {
        method: "POST",
        headers: {
          Title: "orca agent",
          Priority: notification.priority,
          Tags: state,
          "Content-Type": "text/plain",
        },
        body: notification.body,
      });
    } catch {
      if (attempt === retryDelays.length) throw new Error("notification request failed");
      await wait(retryDelays[attempt]);
      continue;
    }

    if (response.ok) return;
    const retryable =
      response.status === 408 || response.status === 429 || (response.status >= 500 && response.status <= 599);
    if (!retryable || attempt === retryDelays.length) {
      throw new Error("notification request failed");
    }
    await wait(retryDelays[attempt]);
  }
}

export default function activate(orca) {
  const lastStates = new Map();

  orca.events.on("agent.status.changed", async (event) => {
    const state = event?.state;
    if (!Object.hasOwn(notifications, state)) return;
    const notification = notifications[state];

    const key = JSON.stringify([event.worktreeId, event.paneKey]);
    if (lastStates.get(key) === state) return;
    lastStates.set(key, state);

    try {
      const topic = (await orca.host.call("secrets.get", { key: "ntfy-topic" }))?.value;
      if (!topic) throw new Error("missing notification secret");
      await sendNotification(topic, state, notification);
    } catch {
      console.error("orca ntfy notification failed");
    }
  });
}
