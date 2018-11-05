'''
Created on Oct 12, 2016

@author: mwittie
'''
import queue
import threading


## wrapper class for a queue of packets
class Interface:
    ## @param maxsize - the maximum size of the queue storing packets
    def __init__(self, maxsize=0):
        self.queue = queue.Queue(maxsize);
        self.mtu = None

    ##get packet from the queue interface
    def get(self):
        try:
            return self.queue.get(False)
        except queue.Empty:
            return None

    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, block=False):
        self.queue.put(pkt, block)


## Implements a network layer packet (different from the RDT packet
# from programming assignment 2).
# NOTE: This class will need to be extended to for the packet to include
# the fields necessary for the completion of this assignment.
class NetworkPacket:
    ## packet encoding lengths
    dst_addr_S_length = 5
    src_addr_S_length = 5
    # flag like in IP header
    flag_length = 1
    # fragmentation offset
    frag_offset_len = 2

    # @param dst_addr: address of the destination host
    # @param data_S: packet payload
    def __init__(self, source_address, dst_addr, data_S, flag=0, frag_offset=0):
        self.src_address = source_address
        self.dst_addr = dst_addr
        self.data_S = data_S
        # set flag
        self.flag = flag
        # set offset
        self.offset = frag_offset

    # called when printing the object
    def __str__(self):
        return self.to_byte_S()

    # convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.src_address).zfill(self.src_addr_S_length)
        byte_S += str(self.dst_addr).zfill(self.dst_addr_S_length)
        # if flag not zero then += flag with new values for new packet
        if self.flag != 0:
            byte_S += str(self.flag).zfill(self.flag_length)
            byte_S += str(self.offset).zfill(self.frag_offset_len)
        # return the data
        byte_S += self.data_S
        return byte_S

    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, mtu, byte_S):
        src_addr = int(byte_S[0: NetworkPacket.src_addr_S_length])
        dst_addr = int(
            byte_S[NetworkPacket.src_addr_S_length: NetworkPacket.src_addr_S_length + NetworkPacket.dst_addr_S_length])
        data_S = byte_S[NetworkPacket.src_addr_S_length + NetworkPacket.dst_addr_S_length:]
        # setting frag to 0 and offset to so as well as creating array to store data if packet is fragmented
        fragment_packs = []
        # use to tell if fragment packet
        fragment = 0
        offset = 0

        # if the size of the packet is larger than our mtu we must fragment it
        if NetworkPacket.flag_length + NetworkPacket.frag_offset_len + len(data_S[offset:]) > mtu:
            fragment = 1
            # fragment packet and set offset for next packet
            while len(data_S[offset:]) != 0:
                # if size is <= mtu set frag to 0 (python did not like <=, split into < and ==)
                if (NetworkPacket.flag_length + NetworkPacket.frag_offset_len + len(data_S[offset:])) < mtu or (
                        NetworkPacket.flag_length + NetworkPacket.frag_offset_len + len(data_S[offset:])) == mtu:
                    fragment = 0
                # get the value of the next offset
                next_offset = offset + mtu - self.flag_length - self.frag_offset_len
                # add new network packet to the fragment packs list
                fragment_packs.append(self(src_addr, dst_addr, data_S[offset:next_offset], fragment, offset))
                # set offset to next_offset
                offset = next_offset
            return fragment_packs
        else:
            return [self(src_addr, dst_addr, data_S, fragment, offset)]
        # end of new network packet


## Implements a network host for receiving and transmitting data
class Host:
    # list to hold fragmented packets
    fragmented_data = []

    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.in_intf_L = [Interface()]
        self.out_intf_L = [Interface()]
        self.stop = False  # for thread termination

    ## called when printing the object
    def __str__(self):
        return 'Host_%s' % (self.addr)

    ## create a packet and enqueue for transmission
    # @param dst_addr: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst_addr, data_S):
        # old packet not being used in splitting the data up
        # p = NetworkPacket(dst_addr, data_S)
        # if is to large then split it up
        if (len(data_S) > self.out_intf_L[0].mtu):
            # max length for text is text - dst_addr length - src_addr length (10)
            max_len = self.out_intf_L[0].mtu - 10
            # split packet into 2 packets with length specidied
            packet_1 = NetworkPacket(self.addr, dst_addr, data_S[0:max_len])  # get data from start0 to our max length
            packet_2 = NetworkPacket(self.addr, dst_addr, data_S[max_len:])  # get all data after our max length
            # send the two packets (copy pasted from original code)
            self.out_intf_L[0].put(packet_1.to_byte_S())  # send packets always enqueued successfully
            print('%s: sending packet "%s" on the out interface with mtu=%d' % (self, packet_1, self.out_intf_L[0].mtu))
            self.out_intf_L[0].put(packet_2.to_byte_S())  # send packets always enqueued successfully
            print('%s: sending packet "%s" on the out interface with mtu=%d' % (self, packet_2, self.out_intf_L[0].mtu))

        # else send data normally
        else:
            # old packet moved here
            p = NetworkPacket(dst_addr, data_S)
            self.out_intf_L[0].put(p.to_byte_S())  # send packets always enqueued successfully
            print('%s: sending packet "%s" on the out interface with mtu=%d' % (self, p, self.out_intf_L[0].mtu))

    ## receive packet from the network layer
    def udt_receive(self):
        pkt_S = self.in_intf_L[0].get()
        # update do deal with fragmented packets
        if pkt_S is not None:
            # if statemen to either add packet to fragment_packs or join the list and send recieved messege
            if pkt_S[NetworkPacket.src_addr_S_length] == '1':
                # add part of frag packet to the list (getting all the data after the initial headers of the packet
                self.fragmented_data.append(
                    pkt_S[
                    NetworkPacket.src_addr_S_length + NetworkPacket.dst_addr_S_length + NetworkPacket.flag_length +
                    NetworkPacket.frag_offset_len:])
            # no more fragments
            else:
                # append data to the fragmented data list
                self.fragmented_data.append(pkt_S[NetworkPacket.src_addr_S_length + NetworkPacket.dst_addr_S_length:])
                # gets the actual flags and other stuff instead of fragmented data
                # join the data stored in the list

                # send recived messege
                print('%s: received packet "%s" on the in interface' % (self, ''.join(self.fragmented_data)))
                # clear the fragmented_packs for next packet
                self.fragmented_data.clear()

    ## thread target for the host to keep receiving data
    def run(self):
        print(threading.currentThread().getName() + ': Starting')
        while True:
            # receive data arriving to the in interface
            self.udt_receive()
            # terminate
            if (self.stop):
                print(threading.currentThread().getName() + ': Ending')
                return


## Implements a multi-interface router described in class
class Router:

    ##@param name: friendly router name for debugging
    # @param intf_count: the number of input and output interfaces
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, intf_count, max_queue_size, forwarding_table):
        self.stop = False  # for thread termination
        self.name = name
        # create a list of interfaces
        self.in_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]
        self.out_intf_L = [Interface(max_queue_size) for _ in range(intf_count)]
        self.forwarding_table = forwarding_table

    ## called when printing the object
    def __str__(self):
        return 'Router_%s' % (self.name)

    ## look through the content of incoming interfaces and forward to
    # appropriate outgoing interfaces
    def forward(self):
        # make sure MTU is set to 30
        self.out_intf_L[0].mtu = 45
        for i in range(len(self.in_intf_L)):
            pkt_S = None
            try:
                # get packet from interface i
                pkt_S = self.in_intf_L[i].get()

                # if packet exists make a forwarding decision
                if pkt_S is not None:
                    p = NetworkPacket.from_byte_S(self.out_intf_L[0].mtu, pkt_S)  # parse a packet out
                    #src = pkt_S[4:5]
                    dst = pkt_S[9:10]  #get the destination of the incoming packet
                    out_route = self.forwarding_table.get(int(dst))
                    # HERE you will need to implement a lookup into the:
                    # forwarding table to find the appropriate outgoing interface
                    # for now we assume the outgoing interface is also i
                    # if p is a list iterate through it, else just do what is done is default network.py
                    ## for all our possible fragment packets (p) do things
                    for x in p:
                        self.out_intf_L[int(out_route)].put(x.to_byte_S(), True)
                        print('%s: forwarding packet "%s" from interface %d to %d with mtu %d' \
                              % (self, x.to_byte_S(), i, out_route, self.out_intf_L[0].mtu))

            except queue.Full:
                print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass

    ## thread target for the host to keep forwarding data
    def run(self):
        print(threading.currentThread().getName() + ': Starting')
        while True:
            self.forward()
            if self.stop:
                print(threading.currentThread().getName() + ': Ending')
                return
