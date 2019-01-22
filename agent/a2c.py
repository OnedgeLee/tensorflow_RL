import numpy as np
import tensorflow as tf
from model import *
import copy

class CNN:
    def __init__(self, sess, window_size, obs_stack, output_size, num_worker, num_step):
        self.sess = sess
        self.window_size = window_size
        self.obs_stack = obs_stack
        self.output_size = output_size

        self.actor = CNNActor('actor', self.window_size, self.obs_stack, self.output_size)
        self.critic = CNNCritic('critic', self.window_size, self.obs_stack)

        self.gamma = 0.99
        self.lamda = 0.9
        self.lr = 0.00025
        self.batch_size = 32
        self.grad_clip_max = 1.0
        self.grad_clip_min = -1.0
        self.cof_entropy = 0.5
        
        self.actor_pi_trainable = self.actor.get_trainable_variables()
        self.critic_pi_trainable = self.critic.get_trainable_variables()

        self.actions = tf.placeholder(dtype=tf.int32,shape=[None])
        self.targets = tf.placeholder(dtype=tf.float32,shape=[None])
        self.adv = tf.placeholder(dtype=tf.float32,shape=[None])
        self.value = tf.squeeze(self.critic.critic)

        act_probs = self.actor.actor

        act_probs = tf.reduce_sum(tf.multiply(act_probs,tf.one_hot(indices=self.actions,depth=self.output_size)),axis=1)
        cross_entropy = tf.log(tf.clip_by_value(act_probs,1e-5, 1.0))*self.adv
        actor_loss = -tf.reduce_mean(cross_entropy)

        critic_loss = tf.losses.mean_squared_error(self.value,self.targets)

        entropy = - self.actor.actor * tf.log(self.actor.actor)
        entropy = tf.reduce_mean(entropy)

        
        total_actor_loss = actor_loss - self.cof_entropy * entropy
        actor_optimizer = tf.train.AdamOptimizer(learning_rate=self.lr)
        self.actor_train_op = actor_optimizer.minimize(total_actor_loss, var_list=self.actor_pi_trainable)

        critic_optimizer = tf.train.AdamOptimizer(learning_rate=self.lr)
        self.critic_train_op = critic_optimizer.minimize(critic_loss, var_list=self.critic_pi_trainable)


    def train_model(self, state, action, targets, advs):
        self.sess.run(self.critic_train_op, feed_dict={self.critic.input: state,
                                                self.targets: targets})
        
        self.sess.run(self.actor_train_op, feed_dict={self.actor.input: state,
                                                self.actions: action,
                                                self.adv: advs})


    def get_action(self, state):
        action = self.sess.run(self.actor.actor, feed_dict={self.actor.input: state})
        action = [np.random.choice(self.output_size, p=i) for i in action]
        return np.stack(action)

    def get_value(self, state, next_state):
        value = self.sess.run(self.value, feed_dict={self.critic.input: state})
        next_value = self.sess.run(self.value, feed_dict={self.critic.input: next_state})
        return value, next_value

    def get_gaes(self, rewards, dones, values, next_values):
        deltas = [r + self.gamma * (1 - d) * nv - v for r, d, nv, v in zip(rewards, dones, next_values, values)]
        deltas = np.stack(deltas)
        gaes = copy.deepcopy(deltas)
        for t in reversed(range(len(deltas) - 1)):
            gaes[t] = gaes[t] + (1 - dones[t]) * self.gamma * self.lamda * gaes[t + 1]

        target = gaes + values
        gaes = (gaes - gaes.mean()) / (gaes.std() + 1e-30)
        return gaes, target