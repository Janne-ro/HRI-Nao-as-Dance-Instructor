# HRI Nao as a Dance Instructor

This repo includes the programs used to devellop the project of Nao as a dance instructor, which utilizes LLMs, data base integration and world modelling via a point cloud to create a social robot for dance education. 

## Structure
The Repo contains the Code subfolder which holds the implementation of the robot whereas the Notebook `Fake_Data_Analysis.ipynb` holds an example analysis that could be used to empirically evaluate the project.
The `functionality_benchmarks.ipynb` holds the examples of functionality benchmarks fo NAO dancing instructor task.
Furthermore the `world_modelling.ipynb` file contains an implementation of the YOLO-framework that is used to implement the robots point cloud.

## How to run
* Run the docker image provided in the code subfolder
* Change the connection in the code to your individual IP-Adress and Port (if Coreograph is run on your local machine)
* Mount the current directory and run the file using Python2 

## Authors
This project was created by the following authors:
* Janne Rotter
* Aimee Lin
* Evgeniia Rumiantseva
All authors contributed equally. 
