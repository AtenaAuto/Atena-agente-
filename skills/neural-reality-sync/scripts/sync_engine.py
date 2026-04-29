import time


def sync_loop(agent, env):
    print("🔱 NRS: Sincronizando picos neurais...")
    while True:
        spike = agent.get_spike()
        if spike:
            env.apply(spike)
        time.sleep(0.001)
