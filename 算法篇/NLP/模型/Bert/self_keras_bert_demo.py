# -*- coding: utf-8- -*-

import numpy as np
from keras.utils import plot_model
from self_keras_bert.bert import load_pretrained_model
from self_keras_bert.utils import SimpleTokenizer, load_vocab


config_path = '/home/liuyongjie/.keras/datasets/chinese_L-12_H-768_A-12/bert_config.json'
checkpoint_path = '/home/liuyongjie/.keras/datasets/chinese_L-12_H-768_A-12/bert_model.ckpt'
dict_path = '/home/liuyongjie/.keras/datasets/chinese_L-12_H-768_A-12/vocab.txt'

token_dict = load_vocab(dict_path) # 读取词典
tokenizer = SimpleTokenizer(token_dict) # 建立分词器
model = load_pretrained_model(config_path, checkpoint_path) # 建立模型，加载权重
print(model.summary())
plot_model(model, to_file="self_bert.png", show_shapes=True)

# 编码测试
token_ids, segment_ids = tokenizer.encode(u'语言模型')
print(model.predict([np.array([token_ids]), np.array([segment_ids])]))





# 情感分析

import json
import numpy as np
import pandas as pd
from random import choice
import re, os
import codecs
from self_keras_bert.bert import load_pretrained_model, set_gelu
from self_keras_bert.utils import SimpleTokenizer, load_vocab
from self_keras_bert.train import PiecewiseLinearLearningRate
set_gelu('tanh') # 切换gelu版本


maxlen = 100
config_path = '/home/liuyongjie/.keras/datasets/chinese_L-12_H-768_A-12/bert_config.json'
checkpoint_path = '/home/liuyongjie/.keras/datasets/chinese_L-12_H-768_A-12/bert_model.ckpt'
dict_path = '/home/liuyongjie/.keras/datasets/chinese_L-12_H-768_A-12/vocab.txt'


neg = pd.read_excel('data/neg.xls', header=None)
pos = pd.read_excel('data/pos.xls', header=None)
chars = {}


data = []

for d in neg[0]:
    data.append((d, 0))
    for c in d:
        chars[c] = chars.get(c, 0) + 1

for d in pos[0]:
    data.append((d, 1))
    for c in d:
        chars[c] = chars.get(c, 0) + 1

chars = {i: j for i, j in chars.items() if j >= 4}


_token_dict = load_vocab(dict_path) # 读取词典
token_dict, keep_words = {}, []

for c in ['[PAD]', '[UNK]', '[CLS]', '[SEP]', '[unused1]']:
    token_dict[c] = len(token_dict)
    keep_words.append(_token_dict[c])

for c in chars:
    if c in _token_dict:
        token_dict[c] = len(token_dict)
        keep_words.append(_token_dict[c])


tokenizer = SimpleTokenizer(token_dict) # 建立分词器


if not os.path.exists('./random_order.json'):
    random_order = list(range(len(data)))
    np.random.shuffle(random_order)
    json.dump(
        random_order,
        open('./random_order.json', 'w'),
        indent=4
    )
else:
    random_order = json.load(open('./random_order.json'))


# 按照9:1的比例划分训练集和验证集
train_data = [data[j] for i, j in enumerate(random_order) if i % 10 != 0]
valid_data = [data[j] for i, j in enumerate(random_order) if i % 10 == 0]


def seq_padding(X, padding=0):
    L = [len(x) for x in X]
    ML = max(L)
    return np.array([
        np.concatenate([x, [padding] * (ML - len(x))]) if len(x) < ML else x for x in X
    ])


class data_generator:
    def __init__(self, data, batch_size=8):
        self.data = data
        self.batch_size = batch_size
        self.steps = len(self.data) // self.batch_size
        if len(self.data) % self.batch_size != 0:
            self.steps += 1
    def __len__(self):
        return self.steps
    def __iter__(self):
        while True:
            idxs = list(range(len(self.data)))
            np.random.shuffle(idxs)
            X1, X2, Y = [], [], []
            for i in idxs:
                d = self.data[i]
                text = d[0][:maxlen]
                x1, x2 = tokenizer.encode(first=text)
                y = d[1]
                X1.append(x1)
                X2.append(x2)
                Y.append([y])
                if len(X1) == self.batch_size or i == idxs[-1]:
                    X1 = seq_padding(X1)
                    X2 = seq_padding(X2)
                    Y = seq_padding(Y)
                    yield [X1, X2], Y
                    [X1, X2, Y] = [], [], []

# 情感分析
from keras.layers import *
from keras.models import Model
import keras.backend as K
from keras.optimizers import Adam


model = load_pretrained_model(
    config_path,
    checkpoint_path,
    keep_words=keep_words,
    albert=True
)

output = Lambda(lambda x: x[:, 0])(model.output)
output = Dense(1, activation='sigmoid')(output)
model = Model(model.input, output)

model.compile(
    loss='binary_crossentropy',
    optimizer=Adam(1e-5),  # 用足够小的学习率
    # optimizer=PiecewiseLinearLearningRate(Adam(1e-5), {1000: 1e-5, 2000: 6e-5}),
    metrics=['accuracy']
)
model.summary()


train_D = data_generator(train_data)
valid_D = data_generator(valid_data)

model.fit_generator(
    train_D.__iter__(),
    steps_per_epoch=len(train_D),
    epochs=10,
    validation_data=valid_D.__iter__(),
    validation_steps=len(valid_D)
)
