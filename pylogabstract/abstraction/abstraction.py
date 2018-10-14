from itertools import combinations
from collections import defaultdict, OrderedDict
# from pylogabstract.clustering.clustering import LogClustering
from pylogabstract.clustering.recursion_clustering import LogClustering
from pylogabstract.preprocess.hamming_similarity import HammingSimilarity
from pylogabstract.parser.parser import Parser
# from pylogabstract.output.output import Output


class LogAbstraction(object):
    def __init__(self):
        # initiate log parsing
        self.parser = Parser()

    @staticmethod
    def __get_asterisk(candidate):
        # candidate: list of list
        abstraction = ''

        # transpose row to column
        candidate_transpose = list(zip(*candidate))
        candidate_length = len(candidate)

        if candidate_length > 1:
            # get abstraction
            abstraction_list = []
            for index, message in enumerate(candidate_transpose):
                message_length = len(set(message))
                if message_length == 1:
                    abstraction_list.append(message[0])
                else:
                    abstraction_list.append('*')

            abstraction = ' '.join(abstraction_list)

        elif candidate_length == 1:
            abstraction = ' '.join(candidate[0])

        return abstraction

    @staticmethod
    def __check_total_asterisk(abstraction1, abstraction2, cluster_id1, cluster_id2):
        # parent_id = smaller cluster merge into this cluster
        # child_id = merged cluster, not processed anymore
        total1 = 0
        total2 = 0
        for word1, word2 in zip(abstraction1, abstraction2):
            if word1 == '*':
                total1 += 1
            if word2 == '*':
                total2 += 1

        parent_id, child_id = -1, -1
        parent_abstraction, child_abstraction = [], []
        if total1 > total2:
            parent_id = cluster_id1
            child_id = cluster_id2
            parent_abstraction = abstraction1
            child_abstraction = abstraction2
        elif total1 < total2:
            parent_id = cluster_id2
            child_id = cluster_id1
            parent_abstraction = abstraction2
            child_abstraction = abstraction1
        elif (total1 == total2) and (total1 > 0) and (total2 > 0):
            parent_id, child_id = -1, -1
            parent_abstraction = abstraction1
            child_abstraction = abstraction2

        return parent_abstraction, child_abstraction, parent_id, child_id

    def __merge_abstraction(self, abstractions):
        checked_abstractions = {}
        cluster_id = 0
        checked_cluster_id = []
        checked_parent_id = []
        valid_combinations = []
        not_merge_id = []

        # get abstraction that will not be checked (merged)
        for original_cluster_id, abstraction in abstractions.items():
            if abstraction['check'] is False:
                checked_abstractions[cluster_id] = {
                    'abstraction': abstractions[original_cluster_id]['abstraction'],
                    'nodes': abstractions[original_cluster_id]['nodes']
                }
                checked_cluster_id.append(original_cluster_id)
                cluster_id += 1

        # get valid combinations
        for cluster_id1, cluster_id2 in combinations(abstractions.keys(), 2):
            if abstractions[cluster_id1]['check'] and abstractions[cluster_id2]['check']:
                valid_combinations.append((cluster_id1, cluster_id2))

        for cluster_id1, cluster_id2 in valid_combinations:
            if (cluster_id1 not in checked_cluster_id) and (cluster_id2 not in checked_cluster_id):
                hs = HammingSimilarity()
                hamming_similarity = hs.get_weighted_hamming(abstractions[cluster_id1]['abstraction'],
                                                             abstractions[cluster_id2]['abstraction'])
                if hamming_similarity > 0.:
                    abstraction1 = abstractions[cluster_id1]['abstraction'].split()
                    abstraction2 = abstractions[cluster_id2]['abstraction'].split()

                    # check parent and child abstraction
                    parent_abstraction, child_abstraction, parent_id, child_id = \
                        self.__check_total_asterisk(abstraction1, abstraction2, cluster_id1, cluster_id2)

                    # check for merge
                    # once merge = False, it will not continue checking
                    merge = False
                    for word1, word2 in zip(parent_abstraction, child_abstraction):
                        if word1 == word2:
                            merge = True
                        elif (word1 != word2) and (word1 == '*'):
                            merge = True
                        elif (word1 != word2) and (word1 != '*') and (word2 != '*'):
                            merge = False
                            break

                    # merge abstractions
                    if merge:
                        if (parent_id != -1) and (child_id != -1):
                            checked_abstractions[cluster_id] = {
                                'abstraction': abstractions[parent_id]['abstraction'],
                                'nodes': abstractions[cluster_id1]['nodes'] + abstractions[cluster_id2]['nodes']
                            }
                            checked_cluster_id.append(child_id)
                            checked_parent_id.append(parent_id)
                            cluster_id += 1
                        else:
                            not_merge_id.extend([cluster_id1, cluster_id2])

                    else:
                        not_merge_id.extend([cluster_id1, cluster_id2])
                else:
                    not_merge_id.extend([cluster_id1, cluster_id2])

        # for cluster id that not in checked_cluster_id and checked_parent_id
        not_merge_id = set(not_merge_id)
        for index in not_merge_id:
            if (index not in checked_cluster_id) and (index not in checked_parent_id):
                checked_abstractions[cluster_id] = {
                    'abstraction': abstractions[index]['abstraction'],
                    'nodes': abstractions[index]['nodes']
                }
                cluster_id += 1

        return checked_abstractions

    @staticmethod
    def __get_partial_logs(nodes, event_attributes, parsed_logs, raw_logs):
        partial_parsed_logs = OrderedDict()
        partial_raw_logs = {}
        for node in nodes:
            for line_index in event_attributes[node]['member']:
                partial_parsed_logs[line_index] = parsed_logs[line_index]
                partial_raw_logs[line_index] = raw_logs[line_index]

        return partial_parsed_logs, partial_raw_logs

    def __get_all_asterisk(self, clusters, event_attributes, parsed_logs, raw_logs):
        # main loop to get asterisk
        # abstractions[message_length] = {cluster_id: abstraction, ...}
        abstractions = {}
        for message_length, clusters in clusters.items():
            abstraction = {}
            for cluster_id, cluster in clusters.items():
                candidate = []
                for node in cluster['nodes']:
                    message = event_attributes[node]['message'].split()
                    candidate.append(message)

                asterisk = self.__get_asterisk(candidate)
                check_asterisk = set(asterisk.replace(' ', ''))

                # run clustering again if abstraction is all asterisk, such as * * * * *
                if check_asterisk == {'*'}:
                    partial_parsed_logs, partial_raw_logs = \
                        self.__get_partial_logs(cluster['nodes'], event_attributes, parsed_logs, raw_logs)
                    log_clustering = LogClustering(partial_parsed_logs, partial_raw_logs)
                    sub_cluster = log_clustering.get_clustering()
                    self.__get_all_asterisk(sub_cluster, event_attributes, parsed_logs, raw_logs)

                else:
                    abstraction[cluster_id] = {'abstraction': asterisk,
                                               'nodes': cluster['nodes'],
                                               'check': cluster['check']}

            # check merge-possible abstraction
            # abstractions[message_length] = self.__merge_abstraction(abstraction)

        return abstractions

    def __get_final_abstraction(self, abstractions, event_attributes, parsed_logs):
        # restart abstraction id from 0, get abstraction and its log ids
        # in this method, we include other fields such as timestamp, hostname, ip address, etc in abstraction
        final_abstractions = {}
        abstraction_id = 0
        for message_length, abstraction in abstractions.items():
            # get log ids per cluster
            for cluster_id, cluster in abstraction.items():
                log_ids = []
                for node in cluster['nodes']:
                    log_ids.extend(event_attributes[node]['member'])

                # get raw logs per cluster (except the main message)
                candidates = defaultdict(list)
                for log_id in log_ids:
                    parsed = parsed_logs[log_id]
                    values = []
                    values_length = 0
                    for label, value in parsed.items():
                        if label != 'message':
                            value_split = value.split()
                            values.extend(value_split)
                            values_length += len(value_split)

                    candidates[values_length].append(values)

                # get asterisk and set final abstraction
                for label_length, candidate in candidates.items():
                    abstraction_str = self.__get_asterisk(candidate)
                    final_abstractions[abstraction_id] = {
                        'abstraction': abstraction_str + ' ' + cluster['abstraction'],
                        'log_id': log_ids   # CHECK AGAIN, not all log_ids
                    }
                    abstraction_id += 1

        return final_abstractions

    def get_abstraction(self, log_file):
        # parsing logs
        parsed_logs, raw_logs = self.parser.parse_logs(log_file)

        # get clusters and event attributes
        # self.clusters[message_length] = {cluster_id: {'nodes': list, 'check': bool}, ...}
        log_clustering = LogClustering(parsed_logs, raw_logs)
        clusters = log_clustering.get_clustering()
        event_attributes = log_clustering.event_attributes

        # get abstraction
        abstractions = self.__get_all_asterisk(clusters, event_attributes, parsed_logs, raw_logs)
        # final_abstractions = self.__get_final_abstraction(abstractions, event_attributes, parsed_logs)

        # final_abstractions[abstraction_id] = {'abstraction': str, 'log_id': [int, ...]}
        # return final_abstractions, raw_logs
        return abstractions, raw_logs

if __name__ == '__main__':
    logfile = '/home/hudan/Git/prlogparser/datasets/casper-rw/syslog.0'
    log_abstraction = LogAbstraction()
    abstraction_results, rawlogs = log_abstraction.get_abstraction(logfile)
    # Output.write_perabstraction(abstraction_results, rawlogs, 'results.txt')
    #
    # for abs_id, abs_data in abstraction_results.items():
    #     print(abs_id, abs_data['abstraction'])
    #     for logid in abs_data['log_id']:
    #         print(rawlogs[logid].rstrip())
    #     print('-----')
