import tensorflow as tf
import numpy as np
from agent import BaseAgent


class PGContinuous(BaseAgent):
    def __init__(self, config, env):
        super(PGContinuous, self).__init__(config, env, 'pg-continuous')

        # ==================== #
        #    Hyper parameters  #
        # ==================== #
        self.learning_rate = self.get_attribute('learning_rate')
        self.gamma = self.get_attribute('gamma')

        # ==================== #
        #        Memory        #
        # ==================== #
        self.batch_size = self.get_attribute('batch_size')
        self.episode_rewards = []
        self.b_obs, self.b_acts, self.b_rews = [], [], []

        # ==================== #
        #        Network       #
        # ==================== #
        self.states, self.actions, self.advantages, self.output, self.normal_dist = self.create_network()
        self.optimiser = self.loss_fn()

        self.session = tf.Session()
        self.session.run(tf.global_variables_initializer())

    def create_network(self):
        states = tf.placeholder(np.float32, shape=[None, self.state_size], name='p_input')
        actions = tf.placeholder(np.float32, shape=[None, self.num_actions])
        advantages = tf.placeholder(np.float32, shape=[None])

        init = tf.random_normal_initializer

        net = tf.layers.dense(inputs=states, units=36, activation=tf.nn.relu, kernel_initializer=init,
                              name='dense_1')
        net = tf.layers.dense(inputs=net, units=36, activation=tf.nn.relu, kernel_initializer=init,
                              name='dense_2')
        sigma = tf.layers.dense(inputs=net, units=1, activation=tf.nn.softplus, kernel_initializer=init)
        mu = tf.layers.dense(inputs=net, units=1, activation=tf.nn.tanh, kernel_initializer=init)

        mu, sigma = mu * 2, sigma + .1
        normal_dist = tf.distributions.Normal(mu, sigma)
        logits = tf.clip_by_value(normal_dist.sample(1), -2, 2)

        return states, actions, advantages, logits, normal_dist

    def loss_fn(self):
        loss = self.normal_dist.log_prob(self.actions) * self.advantages
        loss += 0.01*self.normal_dist.entropy()
        return tf.train.AdamOptimizer(self.learning_rate).minimize(-loss)

    def step(self, render=False):
        if render:
            self.env.render()

        action = self.get_action(self.current_state)

        next_state, reward, done, _ = self.env.step(action)  # observe the results from the action

        self.add(self.current_state, action, reward, None, None)

        self.current_state = next_state

        if done:
            advantages = self.discount_rewards(self.episode_rewards)
            self.b_rews.extend(advantages)

            self.episode_rewards = []

            if self.episode % self.batch_size == 0 and self.episode > 0:
                self.train()

        return reward, done

    def run(self, state):
        return self.session.run(self.output, {self.states: [state]})[0][0]

    def get_action(self, current_state):
        return self.run(current_state)

    def train(self):
        states, actions, ads = self.get()
        self.session.run(self.optimiser, feed_dict={self.states: states, self.actions: actions, self.advantages: ads})
        self.clear_memory()

    def save(self):
        pass

    def load(self):
        pass

    def add(self, current_state, action, reward, done, next_state):
        self.b_obs.append(self.current_state)
        self.b_acts.append(action)
        self.episode_rewards.append(reward)

    def get(self):
        self.b_rews = (self.b_rews - np.mean(self.b_rews)) // (np.std(self.b_rews) + 1e-10)
        return self.b_obs, self.b_acts, self.b_rews

    def clear_memory(self):
        self.b_obs, self.b_acts, self.b_rews = [], [], []

    def discount_rewards(self, r):
        """ take 1D float array of rewards and compute discounted reward """
        discounted_r = np.zeros_like(r)
        running_add = 0
        for t in reversed(xrange(0, len(r))):
            running_add = running_add * self.gamma + r[t]
            discounted_r[t] = running_add

        return discounted_r

    def __str__(self):
        return 'pg-continuous'
