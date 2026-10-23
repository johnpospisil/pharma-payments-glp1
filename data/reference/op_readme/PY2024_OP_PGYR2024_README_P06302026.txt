Filename: OP_PGYR2024_README_P06302026.txt
Version: 1.0
Date: June 2026

1. Program Year 2024 Data Files 

This data set includes records submitted for Program Year 2024 that have been matched with total confidence to a particular covered recipient (i.e., physician, non-physician practitioner or teaching hospital) and displays information about that recipient. This data set includes the most recent attested-to data for Program Year 2024 as of May 30, 2026.  

The data set contained in the comma-separated value (CSV) file includes only the data that is eligible for publication. Consult the Open Payments Methodology and Data Dictionary Document for an explanation of the criteria that the Centers for Medicare and Medicaid Services (CMS) used to determine what data to publish. This document can be found on the Resources page of the Open Payments website (https://www.cms.gov/OpenPayments/Resources). The Methodology and Data Dictionary Document also includes information on the data collection and reporting methodology, data fields included in the files, and any notes or special considerations that users should be aware of.

Each record in the General Payment, Research Payment, and Ownership/Investment files includes a Change Type indicator field. The Change Type value indicator fields are: NEW, ADD, CHANGED, and UNCHANGED.
•	NEW – It indicates that the record is newly reported by the reporting entity since the last publication and is being published for the first time. 
•	ADD – It indicates that the record is not new in the system but, due to the record not being eligible for publication until the current publication cycle, is being published for the first time.
•	CHANGED – It indicates that the record was previously published but has been modified since its last publication. A record whose only change since the last publication is a change to its dispute status is categorized as a changed record. 
•	UNCHANGED - indicates that the record was published during the last publication cycle and is being republished without any change in the current publication. 

Each record in the Removed and Deleted Records file also includes a Change Type indicator field. The Change Type value indicator fields are: DELETED and REMOVED.

•	DELETED – It indicates the previously published record was deleted from the Open Payments system by the reporting entity. 
•	REMOVED – It indicates that the previously published record was removed from the current publication as a result of the reporting entity making updates to the record, which made the record ineligible for publication.

In the event there are no REMOVED or DELETED records for this program year, the Removed and Deleted Records empty file will be included in the compressed (.zip) file.

2. Considerations for using the CSV Files 

Microsoft Excel removes leading zeroes from data fields in CSV files. Certain fields in these data sets may have leading zeroes. These zeroes will be missing when viewing the information within Microsoft Excel. 

Additionally, the latest versions of Microsoft Excel cannot display data sets with more than 1,048,576 rows. Some of these CSV files may exceed that limit. Displaying the data in its entirety may require the use of spreadsheet programs capable of handling very large numbers of records.

3. Details about the Datasets Included in this PGYR2024_P06302026_06032026.zip file

This compressed (.zip) file contains four (3) comma-separated values (CSV) files that use commas as delimiters and one (1) README.txt file. Descriptions of each file contained in this compressed (.zip) file are provided below.

File #1 - OP_DTL_GNRL_PGYR2024_P06302026_06032026.csv: 
This file contains the data set of General Payments reported for the 2024 program year. General Payments are defined as payments or other transfers of value made to a covered recipient (physician, non-physician practitioner or teaching hospital) that are not made in connection with a research agreement or research protocol. 

File #2 - OP_DTL_RSRCH_PGYR2024_P06302026_06032026.csv:
This file contains the data set of Research Payments reported for the 2024 program year. Research Payments are defined as payments or other transfers of value made in connection with a research agreement or research protocol.

File #3 - OP_DTL_OWNRSHP_PGYR2024_P06302026_06032026.csv:
This file contains the data set of Ownership and Investment Interest Information reported for the 2024 program year. Ownership and Investment Interest Information is defined as information on the value of ownership or investment interests that a physician or an immediate family member of a physician held in an applicable manufacturer or applicable group purchasing organization (GPO).  

4. A Covered Recipient Profile Supplement file is also available, which contains information for physicians including principal investigators indicated as recipients of payments. This Covered Recipient Profile Supplement file can be found as a separate zip file: PHPRFL_P06302026_06032026.zip.


For more details, refer to the ReadMe file associated with the Covered Recipient Profile Supplement file: OP_CVRD_RCPNT_PRFL_SPLMTL_README_P06302026.txt

