import os
import json
from EquationGenerator import EquationGenerator
from Interpolate import Interpolate


class EmissionsJsonReader:
    def __init__(self):
        # public values
        self.type = ""
        self.ssc_name = ""
        self.subsegment = ""
        self.tec_name = ""
        self.slope = 0
        self.load = ""
        self.velocity = 0
        self.data = {}

        # private values
        self.result_type = []

        # Result from filter
        self.filtred_tec_name = []

        self.__load_input_data()
        self.__filter_input_to_tec_name()

    @staticmethod
    def __read_json_file():
        converted_json = os.path.join(os.path.dirname(__file__), 'convertedData.json')
        with open(converted_json) as data_file:
            data = json.load(data_file)
        return data

    def set_input_file(self):
        pass

    def set_type(self, value):
        self.type = value
        self.result_type = list(filter(lambda type: type["Name"] == self.type, self.data["Type"]))

    def get_types(self):
        self.data = self.__read_json_file()
        types = []
        for i in range(len(self.data["Type"])):
            types.append(self.data["Type"][i]["Name"])
        return types

    def get_ssc_names(self):
        ssc_names = []
        for i in range(len(self.result_type[0]['SSC_NAME'])):
            ssc_names.append(self.result_type[0]['SSC_NAME'][i]['Name'])
        return ssc_names

    def __load_input_data(self):
        input_data = os.path.join(os.path.dirname(__file__), 'inputData.txt')
        f = open(input_data, "r")
        data = f.read().split(";")
        self.type = data[0]
        self.ssc_name = data[1]
        self.subsegment = data[2]
        self.tec_name = data[3]
        # self.slope = data[4]
        self.load = data[5]
        # self.velocity = int(data[6])

    def __filter_input_to_tec_name(self):
        converted_json = os.path.join(os.path.dirname(__file__), 'convertedData.json')
        with open(converted_json) as data_file:
            data = json.load(data_file)

        type = list(filter(lambda type: type["Name"] == self.type, data["Type"]))
        ssc_name = list(filter(lambda sscName: sscName["Name"] == self.ssc_name, type[0]["SSC_NAME"]))
        subsegment = list(filter(lambda subseg: subseg["Name"] == self.subsegment, ssc_name[0]["Subsegment"]))
        self.filtred_tec_name = list(filter(lambda tecName: tecName["Name"] == self.tec_name, subsegment[0]["TEC_NAME"]))

    def __get_emission_for_pollutant(self, pollutant_value, slope_value):
        slope = list(filter(lambda slope: slope["id"] == str(slope_value), self.filtred_tec_name[0]["Slope"]))
        load = list(filter(lambda load: load["id"] == self.load, slope[0]["Load"]))
        pollutant_data = list(filter(lambda load: load["id"] == pollutant_value, load[0]["Pollutant"]))
        emission = EquationGenerator(pollutant_data[0], self.velocity).get_result()
        return emission

    def get_emission_for_pollutant(self, pollutant):
        # slopes = [-6.0, -4.0, -2.0, -1.0, 0, 2, 4, 6]
        positive_slopes = [0, 2, 4, 6]
        negative_slopes = [-6, -4, -2, 0]
        if self.slope in positive_slopes or self.slope in negative_slopes:
            # slope = filter(lambda slope: slope["id"] == str(self.slope), self.filtred_tec_name[0]["Slope"])
            # load = filter(lambda load: load["id"] == self.load, slope[0]["Load"])
            # pollutant_data = filter(lambda load: load["id"] == pollutant, load[0]["Pollutant"])
            # emission = EquationGenerator(pollutant_data[0], self.velocity).get_result()
            return self.__get_emission_for_pollutant(pollutant, int(self.slope))
        else:
            slopes_for_polutant = []
            if self.slope > 0.0:
                for i in range(len(positive_slopes)):
                    slopes_for_polutant.append(self.__get_emission_for_pollutant(pollutant, positive_slopes[i]))
                i = Interpolate(positive_slopes, slopes_for_polutant)
                return i[self.slope]
            else:
                for i in range(len(negative_slopes)):
                    slopes_for_polutant.append(self.__get_emission_for_pollutant(pollutant, negative_slopes[i]))
                i = Interpolate(negative_slopes, slopes_for_polutant)
                return i[self.slope]

if __name__ == "__main__":
    EmissionsJsonReader()