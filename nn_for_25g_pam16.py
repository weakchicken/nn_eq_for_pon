import torch
import pandas
import numpy
from torch.autograd import Variable
from torch.utils.data import Dataset, DataLoader
import torch.optim as optim
import torch.nn as nn
import matplotlib.pyplot as plt
import time


def main(rop):
    print('Starting time is ' + time.strftime('%Y-%m-%d %H:%M:%S'))
    # Hyper Parameters
    up_sample_rate = 16
    batch_size = 512
    dropout_prob = 0.1
    weight_decay = 0
    learning_rate = 0.1
    window = 101
    epoch_num = 200

    # Prepare trainset & testset
    class RxDataset(Dataset):
        def __init__(self, rx_data, tx_data, window=101):
            self.rx_data = rx_data
            self.tx_data = tx_data
            self.window = window
            if window % 2 is 0:
                self.window = 101
                print('WARNING: the window cannot be even. reset to 101.')

        def __len__(self):
            return self.tx_data.shape[0] - self.window + 1

        def __getitem__(self, idx):
            rx_window = self.rx_data[idx: idx + self.window, 0]
            offset = int((self.window - 1) / 2)
            tx_symbol = self.tx_data[idx + offset, 0]
            return rx_window, tx_symbol

    seq = torch.randperm(10)
    for i in seq[0:6]:
        file_name = '.\\data\\' + str(rop) + 'dBm' + str(i) + '.csv'
        if i == seq[0]:
            rx_data = pandas.read_csv(file_name, sep=',', header=None) \
                            .values[::up_sample_rate]
        else:
            rx_data = numpy.concatenate(
                (rx_data,
                 pandas.read_csv(file_name, sep=',', header=None)
                       .values[::up_sample_rate]),
                axis=0
            )
    tx_data = pandas.read_csv('.\\data\\prbs15pam16.csv',
                              sep=',',
                              header=None) \
                    .values
    tx_data = numpy.tile(tx_data, (6, 1))
    train_dataset = RxDataset(rx_data, tx_data, window=window)
    train_dataloader = DataLoader(train_dataset,
                                  batch_size=batch_size,
                                  shuffle=True)
    for i in seq[6:8]:
        file_name = '.\\data\\' + str(rop) + 'dBm' + str(i) + '.csv'
        if i == seq[6]:
            rx_data = pandas.read_csv(file_name, sep=',', header=None) \
                            .values[::up_sample_rate]
        else:
            rx_data = numpy.concatenate(
                (rx_data,
                 pandas.read_csv(file_name, sep=',', header=None)
                       .values[::up_sample_rate]),
                axis=0
            )
    tx_data = pandas.read_csv('.\\data\\prbs15pam16.csv',
                              sep=',',
                              header=None) \
                    .values
    tx_data = numpy.tile(tx_data, (2, 1))
    cv_dataset = RxDataset(rx_data, tx_data, window=window)
    cv_dataloader = DataLoader(cv_dataset,
                               batch_size=batch_size,
                               shuffle=True)

    for i in seq[8:10]:
        file_name = '.\\data\\' + str(rop) + 'dBm' + str(i) + '.csv'
        if i == seq[8]:
            rx_data = pandas.read_csv(file_name, sep=',', header=None) \
                            .values[::up_sample_rate]
        else:
            rx_data = numpy.concatenate(
                (rx_data,
                 pandas.read_csv(file_name, sep=',', header=None)
                       .values[::up_sample_rate]),
                axis=0
            )
    tx_data = pandas.read_csv('.\\data\\prbs15pam16.csv',
                              sep=',',
                              header=None) \
                    .values
    tx_data = numpy.tile(tx_data, (2, 1))
    test_dataset = RxDataset(rx_data, tx_data, window=window)
    test_dataloader = DataLoader(test_dataset,
                                 batch_size=batch_size,
                                 shuffle=True)

    # Define the network structure
    # TODO Change the network structure
    class Net(nn.Module):
        def __init__(self):
            super(Net, self).__init__()
            self.conv1 = nn.Conv1d(1, 6, 5)
            self.conv1.double()
            self.conv2 = nn.Conv1d(6, 16, 5)
            self.conv2.double()
            # TODO change the input_channel of fc1 if window is changed
            self.fc1 = nn.Linear(16 * 93, 600)
            self.fc1.double()
            self.fc2 = nn.Linear(600, 120)
            self.fc2.double()
            self.fc3 = nn.Linear(120, 84)
            self.fc3.double()
            self.fc4 = nn.Linear(84, 16)
            self.fc4.double()
            self.activation = nn.ReLU()
            self.dropout = nn.Dropout(p=dropout_prob)
            # For SELU only
            # nn.init.normal(list(self.conv1.parameters())[0], std=1/5)
            # nn.init.normal(list(self.conv2.parameters())[0], std=1/5)
            # nn.init.normal(list(self.fc1.parameters())[0], std=1/(16*93))
            # nn.init.normal(list(self.fc2.parameters())[0], std=1/120)
            # nn.init.normal(list(self.fc3.parameters())[0], std=1/84)

        def forward(self, x):
            x = x.unsqueeze(1)
            x = self.activation(self.conv1(x))
            x = self.dropout(x)
            x = self.activation(self.conv2(x))
            x = self.dropout(x)
            x = x.view(-1, self.num_flat_features(x))
            x = self.activation(self.fc1(x))
            x = self.dropout(x)
            x = self.activation(self.fc2(x))
            x = self.dropout(x)
            x = self.activation(self.fc3(x))
            x = self.dropout(x)
            x = self.fc4(x)
            x = self.dropout(x)
            return x

        def num_flat_features(self, x):
            size = x.size()[1:]  # all dimensions except the batch dimension
            num_features = 1
            for s in size:
                num_features *= s
            return num_features

    net = Net()
    net.cuda()
    print(net)
    criterion = nn.CrossEntropyLoss()
    # optimizer = optim.SGD(net.parameters(), lr=0.003)
    optimizer = optim.SGD(net.parameters(),
                          lr=learning_rate,
                          weight_decay=weight_decay)

    def cal_pam16_biterror(predicted, target):
        """Calculate the bit error of PAM8 using Grey coding

        Args:
            predicted (torch.Tensor): The predicted PAM8 sequence
            target (torch.Tensor): The target PAM8 sequence

        Returns:
            int: The bit error between the predicted and target PAM8 sequence
        """
        temp = torch.abs(predicted - target)
        temp[temp == 0] = 0
        temp[temp == 1] = 1
        temp[temp == 2] = 2
        # delta = 3
        temp[(predicted == 7) & (target == 4)] = 1
        temp[(predicted == 4) & (target == 7)] = 1
        temp[(predicted == 6) & (target == 3)] = 3
        temp[(predicted == 3) & (target == 6)] = 3
        temp[(predicted == 5) & (target == 2)] = 1
        temp[(predicted == 2) & (target == 5)] = 1
        temp[(predicted == 4) & (target == 1)] = 3
        temp[(predicted == 1) & (target == 4)] = 3
        temp[(predicted == 3) & (target == 0)] = 1
        temp[(predicted == 0) & (target == 3)] = 1
        temp[(predicted == 5) & (target == 8)] = 3
        temp[(predicted == 8) & (target == 5)] = 3
        temp[(predicted == 6) & (target == 9)] = 1
        temp[(predicted == 9) & (target == 6)] = 1
        temp[(predicted == 7) & (target == 10)] = 3
        temp[(predicted == 10) & (target == 7)] = 3
        temp[(predicted == 8) & (target == 11)] = 1
        temp[(predicted == 11) & (target == 8)] = 1
        temp[(predicted == 9) & (target == 12)] = 3
        temp[(predicted == 12) & (target == 9)] = 3
        temp[(predicted == 10) & (target == 13)] = 1
        temp[(predicted == 13) & (target == 10)] = 1
        temp[(predicted == 11) & (target == 14)] = 3
        temp[(predicted == 14) & (target == 11)] = 3
        temp[(predicted == 12) & (target == 15)] = 1
        temp[(predicted == 15) & (target == 12)] = 1
        # delta = 4
        temp[temp == 4] = 2
        # delta = 5
        temp[(predicted == 0) & (target == 5)] = 3
        temp[(predicted == 5) & (target == 0)] = 3
        temp[(predicted == 1) & (target == 6)] = 1
        temp[(predicted == 6) & (target == 1)] = 1
        temp[(predicted == 2) & (target == 7)] = 3
        temp[(predicted == 7) & (target == 2)] = 3
        temp[(predicted == 3) & (target == 8)] = 3
        temp[(predicted == 8) & (target == 3)] = 3
        temp[(predicted == 4) & (target == 9)] = 3
        temp[(predicted == 9) & (target == 4)] = 3
        temp[(predicted == 5) & (target == 10)] = 1
        temp[(predicted == 10) & (target == 5)] = 1
        temp[(predicted == 6) & (target == 11)] = 3
        temp[(predicted == 11) & (target == 6)] = 3
        temp[(predicted == 7) & (target == 12)] = 3
        temp[(predicted == 12) & (target == 7)] = 3
        temp[(predicted == 8) & (target == 13)] = 3
        temp[(predicted == 13) & (target == 8)] = 3
        temp[(predicted == 9) & (target == 14)] = 1
        temp[(predicted == 14) & (target == 9)] = 1
        temp[(predicted == 10) & (target == 15)] = 3
        temp[(predicted == 15) & (target == 10)] = 3
        # delta = 6
        temp[(predicted == 0) & (target == 6)] = 2
        temp[(predicted == 6) & (target == 0)] = 2
        temp[(predicted == 1) & (target == 7)] = 2
        temp[(predicted == 7) & (target == 1)] = 2
        temp[(predicted == 2) & (target == 8)] = 4
        temp[(predicted == 8) & (target == 2)] = 4
        temp[(predicted == 3) & (target == 9)] = 4
        temp[(predicted == 9) & (target == 3)] = 4
        temp[(predicted == 4) & (target == 10)] = 2
        temp[(predicted == 10) & (target == 4)] = 2
        temp[(predicted == 5) & (target == 11)] = 2
        temp[(predicted == 11) & (target == 5)] = 2
        temp[(predicted == 6) & (target == 12)] = 4
        temp[(predicted == 12) & (target == 6)] = 4
        temp[(predicted == 7) & (target == 13)] = 4
        temp[(predicted == 13) & (target == 7)] = 4
        temp[(predicted == 8) & (target == 14)] = 2
        temp[(predicted == 14) & (target == 8)] = 2
        temp[(predicted == 9) & (target == 15)] = 2
        temp[(predicted == 15) & (target == 9)] = 2
        # delta = 7
        temp[(predicted == 0) & (target == 7)] = 1
        temp[(predicted == 7) & (target == 0)] = 1
        temp[(predicted == 1) & (target == 8)] = 3
        temp[(predicted == 8) & (target == 1)] = 3
        temp[(predicted == 2) & (target == 9)] = 3
        temp[(predicted == 9) & (target == 2)] = 3
        temp[(predicted == 3) & (target == 10)] = 3
        temp[(predicted == 10) & (target == 3)] = 3
        temp[(predicted == 4) & (target == 11)] = 1
        temp[(predicted == 11) & (target == 4)] = 1
        temp[(predicted == 5) & (target == 12)] = 3
        temp[(predicted == 12) & (target == 5)] = 3
        temp[(predicted == 6) & (target == 13)] = 3
        temp[(predicted == 13) & (target == 6)] = 3
        temp[(predicted == 7) & (target == 14)] = 3
        temp[(predicted == 14) & (target == 7)] = 3
        temp[(predicted == 8) & (target == 15)] = 1
        temp[(predicted == 15) & (target == 8)] = 1
        # delta = 8
        temp[temp == 8] = 2
        # delta = 9
        temp[(predicted == 0) & (target == 9)] = 3
        temp[(predicted == 9) & (target == 0)] = 3
        temp[(predicted == 1) & (target == 10)] = 3
        temp[(predicted == 10) & (target == 1)] = 3
        temp[(predicted == 2) & (target == 11)] = 3
        temp[(predicted == 11) & (target == 2)] = 3
        temp[(predicted == 3) & (target == 12)] = 1
        temp[(predicted == 12) & (target == 3)] = 1
        temp[(predicted == 4) & (target == 13)] = 3
        temp[(predicted == 13) & (target == 4)] = 3
        temp[(predicted == 5) & (target == 14)] = 3
        temp[(predicted == 14) & (target == 5)] = 3
        temp[(predicted == 6) & (target == 15)] = 3
        temp[(predicted == 15) & (target == 6)] = 3
        # delta = 10
        temp[(predicted == 0) & (target == 10)] = 4
        temp[(predicted == 10) & (target == 0)] = 4
        temp[(predicted == 1) & (target == 11)] = 4
        temp[(predicted == 11) & (target == 1)] = 4
        temp[(predicted == 2) & (target == 12)] = 2
        temp[(predicted == 12) & (target == 2)] = 2
        temp[(predicted == 3) & (target == 13)] = 2
        temp[(predicted == 13) & (target == 3)] = 2
        temp[(predicted == 4) & (target == 14)] = 4
        temp[(predicted == 14) & (target == 4)] = 4
        temp[(predicted == 5) & (target == 15)] = 4
        temp[(predicted == 15) & (target == 5)] = 4
        # delta = 11
        temp[(predicted == 0) & (target == 11)] = 3
        temp[(predicted == 11) & (target == 0)] = 3
        temp[(predicted == 1) & (target == 12)] = 3
        temp[(predicted == 12) & (target == 1)] = 3
        temp[(predicted == 2) & (target == 13)] = 1
        temp[(predicted == 13) & (target == 2)] = 1
        temp[(predicted == 3) & (target == 14)] = 3
        temp[(predicted == 14) & (target == 3)] = 3
        temp[(predicted == 4) & (target == 15)] = 3
        temp[(predicted == 15) & (target == 4)] = 3
        # delta = 12
        temp[temp == 12] = 2
        # delta = 13
        temp[(predicted == 0) & (target == 13)] = 3
        temp[(predicted == 13) & (target == 0)] = 3
        temp[(predicted == 1) & (target == 14)] = 1
        temp[(predicted == 14) & (target == 1)] = 1
        temp[(predicted == 2) & (target == 15)] = 3
        temp[(predicted == 15) & (target == 2)] = 3
        # delta = 14
        temp[temp == 14] = 2
        # delta = 15
        temp[temp == 15] = 2
        return temp.sum()

    # Training
    print('Start Training....')
    train_loss = []
    train_ber = []
    cv_loss = []
    cv_ber = []
    for epoch in range(epoch_num):  # loop over the dataset multiple times
        # train
        net.train()
        for data in train_dataloader:
            # get the inputs
            rx_window, tx_symbol = data
            rx_window = Variable(rx_window.cuda())
            tx_symbol = Variable(tx_symbol.cuda())
            # zero the parameter gradients
            optimizer.zero_grad()
            # forward + backward + optimize
            outputs = net(rx_window)
            loss = criterion(outputs, tx_symbol)
            loss.backward()
            optimizer.step()

        net.eval()
        # calculate train loss and acc
        running_loss = 0.0
        error = 0
        total = 0
        for data in train_dataloader:
            # get the inputs
            rx_window, tx_symbol = data
            rx_window = Variable(rx_window.cuda())
            tx_symbol = Variable(tx_symbol.cuda())
            # forward + backward + optimize
            outputs = net(rx_window)
            loss = criterion(outputs, tx_symbol)
            running_loss += loss.data[0]
            _, predicted = torch.max(outputs.data, 1)
            total += 4 * batch_size
            error += cal_pam16_biterror(predicted, tx_symbol.data)
        train_loss.append(running_loss / len(train_dataloader))
        train_ber.append(error / total)
        print('#%d epoch train loss: %e train BER: %e' %
              (epoch + 1, train_loss[-1], train_ber[-1]))

        # calculate cv loss and acc
        running_loss = 0.0
        error = 0
        total = 0
        for data in cv_dataloader:
            # get the inputs
            rx_window, tx_symbol = data
            rx_window = Variable(rx_window.cuda())
            tx_symbol = Variable(tx_symbol.cuda())
            # forward + backward + optimize
            outputs = net(rx_window)
            loss = criterion(outputs, tx_symbol)
            running_loss += loss.data[0]
            _, predicted = torch.max(outputs.data, 1)
            total += 4 * batch_size
            error += cal_pam16_biterror(predicted, tx_symbol.data)

        cv_loss.append(running_loss / len(cv_dataloader))
        cv_ber.append(error / total)
        print('#%d epoch cv    loss: %e cv    BER: %e' %
              (epoch + 1, cv_loss[-1], cv_ber[-1]))
        print()
    print('Finished Training....')
    # Testing
    print('Start Testing....')
    error = 0
    total = 0
    for data in test_dataloader:
        rx_window, tx_symbol = data
        rx_window = Variable(rx_window.cuda())
        tx_symbol = Variable(tx_symbol.cuda())
        outputs = net(rx_window)
        _, predicted = torch.max(outputs.data, 1)
        total += 4 * batch_size
        error += cal_pam16_biterror(predicted, tx_symbol.data)
    test_ber = error / total
    print('The test BER is %e' % test_ber)
    print('Finished Testing....')
    print('Ending time is ' + time.strftime('%Y-%m-%d %H:%M:%S'))
    # draw the loss and acc curve
    plt.figure()
    plt.plot(range(len(train_loss)), train_loss, 'r',
             range(len(cv_loss)), cv_loss, 'b')
    plt.title("Loss Learning Curve")
    plt.yscale('log')
    plt.savefig(str(rop) + '_loss.jpg')
    plt.figure()
    plt.plot(range(len(train_ber)), train_ber, 'r',
             range(len(cv_ber)), cv_ber, 'b')
    plt.title("BER Learning Curve")
    plt.yscale('log')
    plt.savefig(str(rop) + '_BER.jpg')
    return test_ber


result = []
rop_list = [2, 1, 0, -1, -2, -3, -4, -6, -7, -8, -9, -10, -11]
for rop in rop_list:
    BER = main(rop)
    result.append(BER)

print()
print('Final result for ' + str(rop_list) + ' dBm:')
print(result)